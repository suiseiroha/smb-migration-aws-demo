"""Server-side Flask sessions backed by DynamoDB instead of local disk.

Flask-Session doesn't ship a DynamoDB backend, so this implements the
same pattern its other backends use: a random session id goes in a
signed cookie, the actual session data lives server-side (here, in
DynamoDB) keyed by that id.

Expected table schema (see infrastructure -- created in milestone 4):
  - Partition key: `session_id` (String)
  - TTL attribute: `expires_at` (Number, epoch seconds)
"""
import secrets
from datetime import datetime, timedelta, timezone

import boto3
from flask.sessions import SessionInterface, SessionMixin
from itsdangerous import BadSignature, URLSafeTimedSerializer
from werkzeug.datastructures import CallbackDict


class ServerSideSession(CallbackDict, SessionMixin):
    def __init__(self, initial=None, sid=None, new=False):
        def on_update(_self):
            _self.modified = True

        super().__init__(initial or {}, on_update)
        self.sid = sid
        self.new = new
        self.modified = False


class DynamoDBSessionInterface(SessionInterface):
    serializer_signer_salt = "dynamodb-session"

    def __init__(self, table_name, region_name, ttl_seconds=3600):
        self.ttl_seconds = ttl_seconds
        self.table = boto3.resource("dynamodb", region_name=region_name).Table(table_name)

    def _signer(self, app):
        return URLSafeTimedSerializer(app.secret_key, salt=self.serializer_signer_salt)

    def open_session(self, app, request):
        cookie_name = app.config["SESSION_COOKIE_NAME"]
        raw = request.cookies.get(cookie_name)
        if not raw:
            return ServerSideSession(sid=secrets.token_urlsafe(32), new=True)

        try:
            sid = self._signer(app).loads(raw, max_age=self.ttl_seconds)
        except BadSignature:
            return ServerSideSession(sid=secrets.token_urlsafe(32), new=True)

        item = self.table.get_item(Key={"session_id": sid}).get("Item")
        if not item:
            return ServerSideSession(sid=sid, new=True)

        return ServerSideSession(initial=item.get("data", {}), sid=sid)

    def save_session(self, app, session, response):
        cookie_name = app.config["SESSION_COOKIE_NAME"]
        domain = self.get_cookie_domain(app)
        path = self.get_cookie_path(app)

        if not session:
            if session.modified:
                self.table.delete_item(Key={"session_id": session.sid})
                response.delete_cookie(cookie_name, domain=domain, path=path)
            return

        if not (session.new or session.modified):
            return

        expires_at = int(
            (datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)).timestamp()
        )
        self.table.put_item(
            Item={
                "session_id": session.sid,
                "data": dict(session),
                "expires_at": expires_at,
            }
        )

        response.set_cookie(
            cookie_name,
            self._signer(app).dumps(session.sid),
            httponly=self.get_cookie_httponly(app),
            domain=domain,
            path=path,
            secure=self.get_cookie_secure(app),
            samesite=self.get_cookie_samesite(app),
            max_age=self.ttl_seconds,
        )
