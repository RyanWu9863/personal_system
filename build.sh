#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# 測試用開發環境的設定跑：獨立的 SQLite，且不套用強制 HTTPS 轉址
DEBUG=True DATABASE_URL="sqlite:///build-test.sqlite3" python manage.py test

python manage.py collectstatic --no-input
python manage.py migrate
