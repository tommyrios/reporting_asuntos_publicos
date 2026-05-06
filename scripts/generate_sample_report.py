from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from news_clusterer import cluster_news, select_top_clusters
from news_models import news_from_dicts
from political_analyzer import generate_political_report
from run_scheduled_report import _preview_text
from google_docs_builder import create_local_docx
from report_numbering import resolve_period
from utils import format_spanish_date, read_json, write_json


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="output/reports/sample")
    parser.add_argument("--input-news", default="templates/sample_news.json")
    args = parser.parse_args()

    tz = ZoneInfo("America/Argentina/Buenos_Aires")
    now = datetime(2026, 5, 1, 20, 0, tzinfo=tz)
    period, start, end = resolve_period(now, period_days=15, mode="half_month_completed")
    period["date_label"] = format_spanish_date(now)
    period["timezone"] = "America/Argentina/Buenos_Aires"
    items = news_from_dicts(read_json(Path(args.input_news), []))
    clusters = select_top_clusters(cluster_news(items, reference=end), min_clusters=4, max_clusters=8)
    report = generate_political_report(clusters, period=period, disable_gemini=True)
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "sample_contract.json", {"period": period, "report": report, "clusters": [c.to_dict() for c in clusters]})
    (out / "sample_preview.txt").write_text(_preview_text(report), encoding="utf-8")
    docx_path = create_local_docx(report, report_id="sample", output_dir=out)
    print(docx_path)


if __name__ == "__main__":
    main()
