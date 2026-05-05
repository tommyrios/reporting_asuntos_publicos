from __future__ import annotations

from typing import Any

from news_models import NewsItem, news_to_dicts


def build_report_contract(
    report_id: str,
    period: dict[str, str],
    selected_news: list[NewsItem],
    analysis: dict[str, Any],
    stats: dict[str, Any],
) -> dict[str, Any]:
    return {
        "report_id": report_id,
        "period": period,
        "analysis": analysis,
        "selected_news": news_to_dicts(selected_news),
        "stats": stats,
        "render_plan": {
            "format": "pptx",
            "slides": ["cover", "analysis", "closing"],
            "editable": True,
        },
    }


def validate_report_contract(report: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    if not report.get("report_id"):
        errors.append("Falta report_id")
    if not isinstance(report.get("period"), dict):
        errors.append("Falta period")
    if not isinstance(report.get("analysis"), dict):
        errors.append("Falta analysis")
    else:
        analysis = report["analysis"]
        for key in ["headline", "executive_vision", "key_developments", "bbva_implications", "watchlist"]:
            if key not in analysis:
                errors.append(f"Falta analysis.{key}")
    if not isinstance(report.get("selected_news"), list):
        errors.append("selected_news debe ser lista")
    elif len(report["selected_news"]) == 0:
        warnings.append("No hay noticias seleccionadas")

    report.setdefault("validation", {})
    report["validation"] = {"errors": errors, "warnings": warnings, "valid": not errors}
    if errors:
        raise ValueError("Contrato inválido: " + "; ".join(errors))
    return report
