"""錄影專用 settings：沿用 demo1.settings，只換資料庫路徑，必要時關閉 Gemini。

用法（CMD）：
    set DEMO_DB_PATH=C:\\small_business_ai_ops\\db_demo_recording.sqlite3
    python manage.py runserver --settings=demo_video.demo_settings

    錄製 B 另外加：set DEMO_DISABLE_GEMINI=1
"""

import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from demo1.settings import *  # noqa: F401,F403  (load_dotenv 在這一行內執行完)
from demo1.settings import BASE_DIR, DATABASES as _BASE_DATABASES

# 這三份檔案不可被錄影流程使用
_PROTECTED_DB_NAMES = {
    "db.sqlite3",
    "db_demo_backup_20261028.sqlite3",
    "db_demo_rehearsal_20261028.sqlite3",
}

_raw_path = os.environ.get("DEMO_DB_PATH", "").strip().strip('"')

if not _raw_path:
    raise ImproperlyConfigured(
        "請先設定 DEMO_DB_PATH，指向錄影專用的 sqlite 檔。"
    )

_db_path = Path(_raw_path)
if not _db_path.is_absolute():
    _db_path = BASE_DIR / _db_path
_db_path = _db_path.resolve()

if _db_path.name.lower() in _PROTECTED_DB_NAMES:
    raise ImproperlyConfigured(
        f"DEMO_DB_PATH 不可指向 {_db_path.name}，請改用錄影專用的複本。"
    )

if not _db_path.is_file():
    raise ImproperlyConfigured(
        f"找不到 DEMO_DB_PATH 指定的檔案：{_db_path}"
    )

DATABASES = {
    **_BASE_DATABASES,
    "default": {**_BASE_DATABASES["default"], "NAME": _db_path},
}

# .env 已由 demo1.settings 載入；在這之後移除金鑰，
# ai_service 讀到的就是「未設定」，完全不會連線 Gemini。
GEMINI_DISABLED = os.environ.get("DEMO_DISABLE_GEMINI", "").strip() == "1"

if GEMINI_DISABLED:
    os.environ.pop("GEMINI_API_KEY", None)

print(
    f"[demo_settings] DB={_db_path} | "
    f"Gemini={'已停用（錄製 B）' if GEMINI_DISABLED else '依 .env 設定（錄製 A）'}",
    file=sys.stderr,
)
