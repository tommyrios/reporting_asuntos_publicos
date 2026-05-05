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

# BBVA 2025 template palette.
BBVA_ELECTRIC_BLUE = "001391"
BBVA_SERENE_BLUE = "85C8FF"
BBVA_MIDNIGHT = "060E46"
BBVA_SAND = "F7F8F8"
BBVA_ICE = "8BE1E9"
BBVA_CANARY = "FFE761"
BBVA_LIME = "88E783"
BBVA_PURPLE = "9694FF"
BBVA_MANDARIN = "FFB56B"
BBVA_GREY_5 = "000519"
BBVA_GREY_4 = "46536D"
BBVA_GREY_3 = "ADB8C2"
BBVA_GREY_2 = "CAD1D8"
BBVA_GREY_1 = "E2E6EA"
BBVA_WHITE = "FFFFFF"

# Backward-compatible aliases used by existing modules.
BBVA_BLUE = BBVA_ELECTRIC_BLUE
BBVA_MEDIUM_BLUE = BBVA_SERENE_BLUE
BBVA_LIGHT_BLUE = BBVA_SERENE_BLUE
BBVA_DARK_TEXT = BBVA_MIDNIGHT
BBVA_MUTED_TEXT = BBVA_GREY_4

TITLE_FONT = "Source Serif 4"
BODY_FONT = "Lato"


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
