#!/usr/bin/env bash
set -o errexit

pip install -r requirements.txt

# 測試用獨立的 SQLite，不碰正式資料庫，也不需要建資料庫的權限
DATABASE_URL="sqlite:///build-test.sqlite3" python manage.py test

python manage.py collectstatic --no-input
python manage.py migrate
