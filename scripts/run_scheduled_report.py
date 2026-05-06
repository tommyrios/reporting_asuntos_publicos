from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from config import (
    CLUSTERS_DIR,
    DEFAULT_PERIOD_DAYS,
    MAX_CLUSTERS,
    MAX_RAW_NEWS,
    MIN_CLUSTERS,
    NORMALIZED_DIR,
    RAW_NEWS_DIR,
    REPORTS_DATA_DIR,
    REPORTS_OUTPUT_DIR,
    REPORT_TIMEZONE,
    REPORT_PERIOD_MODE,
    SOURCES_CONFIG_PATH,
    ensure_project_dirs,
)
from google_docs_builder import create_google_doc
from news_clusterer import cluster_news, select_top_clusters
from news_collector import collect_news
from news_models import clusters_to_dicts, news_from_dicts, news_to_dicts
from political_analyzer import generate_political_report
from report_numbering import resolve_period
from send_email import send_email
from utils import format_spanish_date, parse_bool, read_json, write_json

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _period(period_days: int, timezone_name: str, mode: str = REPORT_PERIOD_MODE) -> tuple[dict[str, str], datetime, datetime]:
    tz = ZoneInfo(timezone_name)
    now = datetime.now(tz)
    period, start, end = resolve_period(now, period_days=period_days, mode=mode)
    period["date_label"] = format_spanish_date(now)
    period["timezone"] = timezone_name
    return period, start, end


def _load_input_news(path: str | None):
    if not path:
        return None
    payload = read_json(Path(path), default=[])
    if not isinstance(payload, list):
        raise RuntimeError(f"El archivo de noticias debe contener una lista: {path}")
    return news_from_dicts(payload)


def run(args: argparse.Namespace) -> dict:
    ensure_project_dirs()
    period, start, end = _period(args.period_days, args.timezone, args.period_mode)
    run_stamp = end.strftime("%Y%m%d_%H%M")
    report_id = f"apuntes_politicos_{run_stamp}"
    out_dir = REPORTS_OUTPUT_DIR / report_id
    out_dir.mkdir(parents=True, exist_ok=True)

    logger.info("event=run_started report_id=%s period=%s", report_id, period["label"])

    raw_items = _load_input_news(args.input_news)
    if raw_items is None:
        raw_items = collect_news(SOURCES_CONFIG_PATH, start=start, end=end, period_days=args.period_days)
    raw_items = raw_items[: args.max_raw_news]

    raw_path = RAW_NEWS_DIR / f"{report_id}.json"
    write_json(raw_path, news_to_dicts(raw_items))

    sources_cfg = read_json(SOURCES_CONFIG_PATH, default={}) or {}
    similarity_threshold = float(sources_cfg.get("clustering", {}).get("title_similarity_threshold", 0.20))
    clusters = cluster_news(raw_items, similarity_threshold=similarity_threshold, reference=end)
    selected_clusters = select_top_clusters(clusters, min_clusters=args.min_clusters, max_clusters=args.max_clusters)

    clusters_path = CLUSTERS_DIR / f"{report_id}.json"
    selected_clusters_path = out_dir / "selected_clusters.json"
    write_json(clusters_path, clusters_to_dicts(clusters))
    write_json(selected_clusters_path, clusters_to_dicts(selected_clusters))

    report = generate_political_report(selected_clusters, period=period, disable_gemini=args.disable_gemini)
    report_contract = {
        "report_id": report_id,
        "period": period,
        "report": report,
        "stats": {
            "raw_news_count": len(raw_items),
            "cluster_count": len(clusters),
            "selected_cluster_count": len(selected_clusters),
            "min_clusters": args.min_clusters,
            "max_clusters": args.max_clusters,
        },
        "selected_clusters": clusters_to_dicts(selected_clusters),
    }

    report_data_path = REPORTS_DATA_DIR / f"{report_id}.json"
    contract_path = out_dir / "report_contract.json"
    write_json(report_data_path, report_contract)
    write_json(contract_path, report_contract)

    local_preview_path = out_dir / "preview.txt"
    local_preview_path.write_text(_preview_text(report), encoding="utf-8")

    doc_result = None
    if args.create_doc:
        doc_result = create_google_doc(report, report_id=report_id)
        report_contract["google_doc"] = doc_result
        write_json(contract_path, report_contract)

    email_result = None
    should_send = args.send_email or parse_bool(os.getenv("SEND_EMAIL"), False)
    if should_send:
        if not doc_result:
            raise RuntimeError("Para enviar email se requiere crear el Google Doc. Usá --create-doc o CREATE_GOOGLE_DOC=true.")
        subject = f"{report['title']} - {report.get('date_label', period['date_label'])}"
        body = (
            "Hola,\n\n"
            "Comparto el enlace al borrador de Apuntes políticos:\n"
            f"{doc_result['document_url']}\n\n"
            "Saludos."
        )
        email_result = send_email(subject, body)
        report_contract["email_result"] = email_result
        write_json(contract_path, report_contract)

    log_payload = {
        "report_id": report_id,
        "period": period,
        "paths": {
            "raw_news": str(raw_path),
            "clusters": str(clusters_path),
            "selected_clusters": str(selected_clusters_path),
            "contract": str(contract_path),
            "preview": str(local_preview_path),
        },
        "google_doc": doc_result,
        "email_result": email_result,
        "stats": report_contract["stats"],
    }
    log_path = out_dir / "run_log.json"
    write_json(log_path, log_payload)
    logger.info("event=run_finished report_id=%s doc_url=%s", report_id, (doc_result or {}).get("document_url", ""))
    return log_payload


def _preview_text(report: dict) -> str:
    lines = [
        "DIRECCIÓN DE RELACIONES INSTITUCIONALES        NOTA INTERNA",
        "",
        report.get("title", "Apuntes políticos"),
        report.get("date_label", ""),
        "",
        report.get("lead", ""),
        "",
    ]
    for item in report.get("developments", []):
        headline = item.get("headline", "").rstrip(".")
        lines.append(f"─ {headline}. {item.get('analysis', '')}")
        lines.append("")
    lines.append("─ Claves prospectivas")
    for key in report.get("prospective_keys", []):
        lines.append(f"  ○ {key}")
    lines.extend(["", "Gracias!", "DIRECCIÓN DE RELACIONES INSTITUCIONALES"])
    return "\n".join(lines)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Genera Apuntes políticos en Google Docs")
    parser.add_argument("--period-days", type=int, default=DEFAULT_PERIOD_DAYS)
    parser.add_argument("--timezone", default=REPORT_TIMEZONE)
    parser.add_argument("--period-mode", default=REPORT_PERIOD_MODE, choices=["sliding", "half_month_current", "current_half_month", "half_month", "half_month_completed", "completed_half_month"], help="Modo de ventana: half_month_current numera por quincena vigente; half_month_completed usa la última quincena cerrada; sliding conserva últimos N días.")
    parser.add_argument("--input-news", help="Archivo JSON local de noticias crudas/normalizadas")
    parser.add_argument("--max-raw-news", type=int, default=MAX_RAW_NEWS)
    parser.add_argument("--min-clusters", type=int, default=MIN_CLUSTERS)
    parser.add_argument("--max-clusters", type=int, default=MAX_CLUSTERS)
    parser.add_argument("--disable-gemini", action="store_true")
    parser.add_argument("--create-doc", action="store_true", default=parse_bool(os.getenv("CREATE_GOOGLE_DOC"), True))
    parser.add_argument("--no-create-doc", dest="create_doc", action="store_false")
    parser.add_argument("--send-email", action="store_true")
    return parser


def main() -> None:
    _setup_logging()
    args = build_arg_parser().parse_args()
    try:
        result = run(args)
    except Exception as exc:
        logger.exception("event=run_failed reason=%s", exc)
        sys.exit(1)
    print((result.get("google_doc") or {}).get("document_url") or result["paths"]["preview"])


if __name__ == "__main__":
    main()
