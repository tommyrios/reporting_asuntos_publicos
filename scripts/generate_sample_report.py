from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from config import REPORT_TIMEZONE, TEMPLATES_DIR, ensure_project_dirs
from deduplicator import deduplicate_news
from news_models import news_from_dicts, news_to_dicts
from political_analyzer import generate_political_analysis
from pptx_builder import create_aapp_pptx
from relevance_scorer import score_news, select_relevant_news
from report_contract import build_report_contract, validate_report_contract
from utils import read_json, write_json


def main() -> None:
    ensure_project_dirs()
    tz = ZoneInfo(REPORT_TIMEZONE)
    end = datetime.now(tz)
    start = end - timedelta(days=15)
    period = {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "label": f"{start.strftime('%d/%m/%Y')} al {end.strftime('%d/%m/%Y')}",
        "timezone": REPORT_TIMEZONE,
        "period_days": "15",
    }
    sample_path = TEMPLATES_DIR / "sample_news.json"
    payload = read_json(sample_path, default=[])
    items = news_from_dicts(payload)
    unique, duplicates = deduplicate_news(items)
    scored = score_news(unique, reference=end)
    selected = select_relevant_news(scored, max_items=4, min_score=1)
    analysis = generate_political_analysis(selected, period=period, disable_gemini=True)
    stats = {
        "raw_news_count": len(items),
        "unique_news_count": len(unique),
        "duplicate_news_count": len(duplicates),
        "previously_used_count": 0,
        "scored_news_count": len(scored),
        "selected_news_count": len(selected),
        "min_relevance_score": 1,
    }
    report = validate_report_contract(build_report_contract("sample", period, selected, analysis, stats))
    out_dir = Path(__file__).resolve().parent.parent / "output" / "reports" / "sample"
    out_dir.mkdir(parents=True, exist_ok=True)
    pptx_path = out_dir / "report_aapp_sample.pptx"
    contract_path = out_dir / "report_contract.json"
    selected_path = out_dir / "selected_news.json"
    create_aapp_pptx(report, pptx_path)
    write_json(contract_path, report)
    write_json(selected_path, news_to_dicts(selected))
    print(pptx_path)


if __name__ == "__main__":
    main()
