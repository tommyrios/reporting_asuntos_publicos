from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from config import (
    DEFAULT_PERIOD_DAYS,
    HISTORY_PATH,
    MAX_NEWS,
    NORMALIZED_NEWS_DIR,
    RAW_NEWS_DIR,
    REPORT_TIMEZONE,
    REPORTS_DIR,
    SELECTED_NEWS,
    SELECTED_NEWS_DIR,
    SOURCES_CONFIG_PATH,
    ensure_project_dirs,
)
from deduplicator import deduplicate_news
from history_manager import filter_used_news, load_history, update_history
from news_collector import collect_news
from news_models import news_from_dicts, news_to_dicts
from political_analyzer import generate_political_analysis
from pptx_builder import create_aapp_pptx
from relevance_scorer import score_news, select_relevant_news
from report_contract import build_report_contract, validate_report_contract
from send_gmail import send_email_with_attachments
from utils import parse_bool, read_json, write_json

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _period(period_days: int, timezone_name: str) -> tuple[dict[str, str], datetime, datetime]:
    tz = ZoneInfo(timezone_name)
    end = datetime.now(tz)
    start = end - timedelta(days=period_days)
    label = f"{start.strftime('%d/%m/%Y')} al {end.strftime('%d/%m/%Y')}"
    return (
        {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "label": label,
            "timezone": timezone_name,
            "period_days": str(period_days),
        },
        start,
        end,
    )


def _load_input_news(path: Path):
    payload = read_json(path, default=[])
    if not isinstance(payload, list):
        raise RuntimeError(f"El archivo de noticias debe contener una lista: {path}")
    return news_from_dicts(payload)


def run(args: argparse.Namespace) -> dict:
    ensure_project_dirs()
    period, start, end = _period(args.period_days, args.timezone)
    run_stamp = end.strftime("%Y%m%d_%H%M")
    report_id = f"aapp_{run_stamp}"
    report_dir = REPORTS_DIR / report_id
    report_dir.mkdir(parents=True, exist_ok=True)

    logger.info("event=run_started report_id=%s period=%s", report_id, period["label"])

    if args.input_news:
        raw_items = _load_input_news(Path(args.input_news))
    else:
        raw_items = collect_news(SOURCES_CONFIG_PATH, start=start, end=end, period_days=args.period_days)

    if len(raw_items) > args.max_news:
        raw_items = raw_items[: args.max_news]

    raw_path = RAW_NEWS_DIR / f"{report_id}.json"
    write_json(raw_path, news_to_dicts(raw_items))

    config = read_json(SOURCES_CONFIG_PATH, default={}) or {}
    threshold = float(config.get("deduplication", {}).get("title_similarity_threshold", 0.88))
    unique_items, duplicate_items = deduplicate_news(raw_items, title_similarity_threshold=threshold)

    history = load_history(HISTORY_PATH)
    fresh_items, used_items = filter_used_news(unique_items, history)

    scored = score_news(fresh_items, reference=end)
    selection_cfg = config.get("selection", {})
    max_selected = int(args.selected_news or selection_cfg.get("max_selected_news", SELECTED_NEWS))
    min_score = int(selection_cfg.get("min_relevance_score", 20))
    selected = select_relevant_news(scored, max_items=max_selected, min_score=min_score)

    normalized_path = NORMALIZED_NEWS_DIR / f"{report_id}.json"
    selected_path = SELECTED_NEWS_DIR / f"{report_id}.json"
    write_json(normalized_path, news_to_dicts(scored))
    write_json(selected_path, news_to_dicts(selected))

    analysis = generate_political_analysis(selected, period=period, disable_gemini=args.disable_gemini)
    stats = {
        "raw_news_count": len(raw_items),
        "unique_news_count": len(unique_items),
        "duplicate_news_count": len(duplicate_items),
        "previously_used_count": len(used_items),
        "scored_news_count": len(scored),
        "selected_news_count": len(selected),
        "min_relevance_score": min_score,
    }
    report = build_report_contract(report_id, period, selected, analysis, stats)
    report = validate_report_contract(report)

    contract_path = report_dir / "report_contract.json"
    sources_path = report_dir / "sources.json"
    selected_report_path = report_dir / "selected_news.json"
    log_path = report_dir / "run_log.json"
    pptx_path = report_dir / f"report_aapp_{run_stamp}.pptx"

    write_json(contract_path, report)
    write_json(sources_path, news_to_dicts(raw_items))
    write_json(selected_report_path, news_to_dicts(selected))
    create_aapp_pptx(report, pptx_path)

    log_payload = {
        "report_id": report_id,
        "period": period,
        "paths": {
            "pptx": str(pptx_path),
            "contract": str(contract_path),
            "sources": str(sources_path),
            "selected_news": str(selected_report_path),
        },
        "stats": stats,
        "email_sent": False,
    }

    if args.update_history and selected:
        update_history(HISTORY_PATH, report_id, selected, metadata={"period": period, "stats": stats})

    should_send = args.send_email or parse_bool(os.environ.get("SEND_EMAIL"), False)
    if should_send:
        subject = f"Informe quincenal AAPP - {period['label']}"
        body = (
            "Hola,\n\n"
            "Adjunto el borrador editable del informe quincenal de Asuntos Públicos. "
            "Incluye el PPTX y los archivos de trazabilidad de fuentes seleccionadas.\n\n"
            "Saludos."
        )
        result = send_email_with_attachments(subject, body, attachments=[pptx_path, contract_path, selected_report_path])
        log_payload["email_sent"] = True
        log_payload["gmail_result"] = result

    write_json(log_path, log_payload)
    logger.info("event=run_finished pptx=%s", pptx_path)
    return log_payload


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Genera el reporte quincenal de Asuntos Públicos")
    parser.add_argument("--period-days", type=int, default=DEFAULT_PERIOD_DAYS)
    parser.add_argument("--timezone", default=REPORT_TIMEZONE)
    parser.add_argument("--input-news", help="Archivo JSON local de noticias normalizadas")
    parser.add_argument("--max-news", type=int, default=MAX_NEWS)
    parser.add_argument("--selected-news", type=int, default=SELECTED_NEWS)
    parser.add_argument("--send-email", action="store_true")
    parser.add_argument("--disable-gemini", action="store_true")
    parser.add_argument("--no-history-update", dest="update_history", action="store_false")
    parser.set_defaults(update_history=True)
    return parser


def main() -> None:
    _setup_logging()
    parser = build_arg_parser()
    args = parser.parse_args()
    try:
        result = run(args)
    except Exception as exc:
        logger.exception("event=run_failed reason=%s", exc)
        sys.exit(1)
    print(result["paths"]["pptx"])


if __name__ == "__main__":
    main()
