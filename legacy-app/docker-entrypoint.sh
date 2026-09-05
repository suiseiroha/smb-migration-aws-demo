#!/bin/sh
set -e

if [ ! -f instance/app.db ]; then
    python seed.py
fi

exec python app.py
