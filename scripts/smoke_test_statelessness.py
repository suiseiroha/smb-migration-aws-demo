"""Proves modern-app is actually stateless and load-balanced correctly,
not just theoretically.

Two parts:
1. Repeatedly hit the ALB, create a customer/invoice/upload, confirm
   everything stays retrievable across many requests -- this is the
   round-robin case, exercising whichever target the ALB happens to
   route to.
2. Deterministically force traffic through each target individually
   (deregister the other one from the target group) and confirm the
   *same* logged-in session and the *same* uploaded file are both
   still there -- this proves it, rather than relying on round-robin
   probability having hit both targets across N requests.

Requires two healthy targets already registered. Restores both targets
at the end regardless of pass/fail.

The ALB and target group are looked up by name at runtime, not
hardcoded -- works the same whether they came from the manual Phase 1
build or the CDK stack, and survives either one being torn down and
recreated (which changes their ARN/DNS name every time).

Usage:
    python scripts/smoke_test_statelessness.py
"""
import io
import re
import sys
import time

import boto3
import requests

REGION = "ap-southeast-1"
ALB_NAME = "smb-migration-demo-alb"
TARGET_GROUP_NAME = "smb-migration-demo-tg"
UPLOAD_BUCKET_NAME = "smb-migration-demo-uploads"


def discover_alb_and_target_group(elbv2):
    alb = elbv2.describe_load_balancers(Names=[ALB_NAME])["LoadBalancers"][0]
    tg = elbv2.describe_target_groups(Names=[TARGET_GROUP_NAME])["TargetGroups"][0]
    return f"http://{alb['DNSName']}", tg["TargetGroupArn"]


def get_csrf(html):
    return re.search(r'name="csrf_token" type="hidden" value="([^"]+)"', html).group(1)


def login(base):
    s = requests.Session()
    r = s.get(f"{base}/login")
    r = s.post(
        f"{base}/login",
        data={"csrf_token": get_csrf(r.text), "username": "admin", "password": "changeme123"},
    )
    assert "Dashboard" in r.text, "login failed"
    return s


def wait_for_target_state(elbv2, target_group_arn, target_id, state, timeout=180):
    start = time.time()
    while time.time() - start < timeout:
        resp = elbv2.describe_target_health(
            TargetGroupArn=target_group_arn, Targets=[{"Id": target_id}]
        )
        if resp["TargetHealthDescriptions"][0]["TargetHealth"]["State"] == state:
            return True
        time.sleep(5)
    return False


def check_still_there(s, base, label):
    r = s.get(f"{base}/customers", allow_redirects=False)
    customer_ok = r.status_code == 200 and "HA Test Co" in r.text

    r = s.get(f"{base}/invoices/1", allow_redirects=False)
    m = re.search(r'href="(/uploads/[^"]+)"', r.text)
    attachment_ok = False
    if m:
        dl = s.get(base + m.group(1), allow_redirects=False)
        attachment_ok = dl.status_code == 302 and UPLOAD_BUCKET_NAME in dl.headers.get("Location", "")

    ok = customer_ok and attachment_ok
    print(f"[{label}] customer visible: {customer_ok}, attachment downloadable: {attachment_ok} -> {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    elbv2 = boto3.client("elbv2", region_name=REGION)
    base, target_group_arn = discover_alb_and_target_group(elbv2)
    print(f"ALB: {base}\nTarget group: {target_group_arn}")

    targets = [
        d["Target"]["Id"]
        for d in elbv2.describe_target_health(TargetGroupArn=target_group_arn)[
            "TargetHealthDescriptions"
        ]
    ]
    print(f"Registered targets: {targets}")
    if len(targets) < 2:
        print("Need 2 registered targets for this test -- scale the ASG to 2 first.")
        sys.exit(1)
    target_a, target_b = targets

    # --- Part 1: create data, repeated round-robin hits ---
    s = login(base)
    r = s.post(
        f"{base}/customers/new",
        data={"csrf_token": get_csrf(s.get(f"{base}/customers/new").text),
              "name": "HA Test Co", "email": "ha-test@example.com", "phone": "", "address": ""},
    )
    assert "Customer created" in r.text
    print("PASS: created customer through the ALB")

    r = s.post(
        f"{base}/invoices/1/edit",
        data={"csrf_token": get_csrf(s.get(f"{base}/invoices/1/edit").text),
              "invoice_number": "INV-1001", "customer_id": "1", "amount": "420.00", "status": "paid"},
        files={"attachment": ("ha-test.png", io.BytesIO(b"ha test bytes"), "image/png")},
    )
    assert r.status_code == 200
    print("PASS: uploaded a file (to S3) through the ALB")

    ok_count = sum(
        1 for _ in range(20)
        if s.get(f"{base}/customers", allow_redirects=False).status_code == 200
    )
    print(f"PASS: {ok_count}/20 repeated requests succeeded with the same session (round-robin)")
    assert ok_count == 20, "session dropped on at least one round-robin request"

    # --- Part 2: deterministic per-target isolation ---
    print(f"\nForcing traffic through {target_a} only (deregistering {target_b})...")
    elbv2.deregister_targets(TargetGroupArn=target_group_arn, Targets=[{"Id": target_b}])
    time.sleep(10)
    ok_a = check_still_there(s, base, f"{target_a} only")

    print(f"\nRe-registering {target_b}, forcing traffic through it only (deregistering {target_a})...")
    elbv2.register_targets(TargetGroupArn=target_group_arn, Targets=[{"Id": target_b}])
    wait_for_target_state(elbv2, target_group_arn, target_b, "healthy")
    elbv2.deregister_targets(TargetGroupArn=target_group_arn, Targets=[{"Id": target_a}])
    time.sleep(10)
    ok_b = check_still_there(s, base, f"{target_b} only")

    print("\nRestoring both targets...")
    elbv2.register_targets(TargetGroupArn=target_group_arn, Targets=[{"Id": target_a}])
    wait_for_target_state(elbv2, target_group_arn, target_a, "healthy")

    print(f"\n{'ALL PASS' if ok_a and ok_b else 'FAIL'}: same session + upload worked through each target independently")
    if not (ok_a and ok_b):
        sys.exit(1)


if __name__ == "__main__":
    main()
