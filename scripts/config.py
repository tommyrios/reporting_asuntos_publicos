from __future__ import annotations

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
OUTPUT_DIR = ROOT_DIR / "output"
PROMPTS_DIR = ROOT_DIR / "prompts"

SOURCES_CONFIG_PATH = DATA_DIR / "config" / "sources.json"
RAW_NEWS_DIR = DATA_DIR / "raw_news"
NORMALIZED_DIR = DATA_DIR / "normalized"
CLUSTERS_DIR = DATA_DIR / "clusters"
REPORTS_DATA_DIR = DATA_DIR / "reports"
REPORTS_OUTPUT_DIR = OUTPUT_DIR / "reports"

REPORT_TIMEZONE = os.getenv("REPORT_TIMEZONE", "America/Argentina/Buenos_Aires")
DEFAULT_PERIOD_DAYS = int(os.getenv("REPORT_PERIOD_DAYS", "15"))
MAX_RAW_NEWS = int(os.getenv("AAPP_MAX_RAW_NEWS", "160"))
MIN_CLUSTERS = int(os.getenv("AAPP_MIN_CLUSTERS", "4"))
MAX_CLUSTERS = int(os.getenv("AAPP_MAX_CLUSTERS", "8"))
REPORT_PERIOD_MODE = os.getenv("REPORT_PERIOD_MODE", "half_month_current")


def ensure_project_dirs() -> None:
    for path in [RAW_NEWS_DIR, NORMALIZED_DIR, CLUSTERS_DIR, REPORTS_DATA_DIR, REPORTS_OUTPUT_DIR]:
        path.mkdir(parents=True, exist_ok=True)
