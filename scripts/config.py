from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_DIR = DATA_DIR / "config"
RAW_NEWS_DIR = DATA_DIR / "raw_news"
NORMALIZED_NEWS_DIR = DATA_DIR / "normalized_news"
SELECTED_NEWS_DIR = DATA_DIR / "selected_news"
HISTORY_DIR = DATA_DIR / "history"
OUTPUT_DIR = BASE_DIR / "output"
REPORTS_DIR = OUTPUT_DIR / "reports"
PROMPTS_DIR = BASE_DIR / "prompts"
ASSETS_DIR = BASE_DIR / "assets"
BRAND_DIR = ASSETS_DIR / "brand"
TEMPLATES_DIR = BASE_DIR / "templates"

SOURCES_CONFIG_PATH = CONFIG_DIR / "sources.json"
HISTORY_PATH = HISTORY_DIR / "used_news.json"

REPORT_TIMEZONE = os.environ.get("REPORT_TIMEZONE", "America/Argentina/Buenos_Aires")
DEFAULT_PERIOD_DAYS = int(os.environ.get("AAPP_PERIOD_DAYS", "15"))
MAX_NEWS = int(os.environ.get("AAPP_MAX_NEWS", "120"))
SELECTED_NEWS = int(os.environ.get("AAPP_SELECTED_NEWS", "12"))

BBVA_BLUE = "072146"
BBVA_MEDIUM_BLUE = "1464A5"
BBVA_LIGHT_BLUE = "5BBEFF"
BBVA_DARK_TEXT = "121212"
BBVA_MUTED_TEXT = "666666"


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_project_dirs() -> None:
    for path in [
        RAW_NEWS_DIR,
        NORMALIZED_NEWS_DIR,
        SELECTED_NEWS_DIR,
        HISTORY_DIR,
        REPORTS_DIR,
    ]:
        ensure_dir(path)
