from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt

from config import (
    BBVA_BLUE,
    BBVA_DARK_TEXT,
    BBVA_GREY_4,
    BBVA_ICE,
    BBVA_LIME,
    BBVA_MANDARIN,
    BBVA_MIDNIGHT,
    BBVA_PURPLE,
    BBVA_SAND,
    BBVA_SERENE_BLUE,
    BBVA_WHITE,
    BODY_FONT,
    BRAND_DIR,
    TITLE_FONT,
)

LOGO_BLUE = BRAND_DIR / "bbva_logo_blue.png"
LOGO_WHITE = BRAND_DIR / "bbva_logo_white.png"
EMOJI_POLITICO = BRAND_DIR / "emoji_politico.png"

SLIDE_W = 13.333
SLIDE_H = 7.5

# Limits are sentence-safe. They never add ellipsis, so text does not look unfinished.
TEXT_LIMITS = {
    "headline": 86,
    "executive_vision": 880,
    "key_developments": 125,
    "bbva_implications": 118,
    "watchlist": 112,
}


def _rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color.replace("#", ""))


def _set_background(slide, hex_color: str) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(hex_color)


def _set_font(
    run,
    font_name: str,
    size: float,
    color: str,
    bold: bool = False,
    italic: bool = False,
) -> None:
    run.font.name = font_name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = _rgb(color)


def _add_logo(slide, color: str, x: float, y: float, width: float) -> None:
    logo = LOGO_WHITE if color == "white" else LOGO_BLUE
    if logo.exists():
        slide.shapes.add_picture(str(logo), Inches(x), Inches(y), width=Inches(width))
        return

    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(width), Inches(0.35))
    p = tb.text_frame.paragraphs[0]
    run = p.add_run()
    run.text = "BBVA"
    _set_font(run, BODY_FONT, 22, BBVA_WHITE if color == "white" else BBVA_BLUE, bold=True)


def _add_textbox(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    font_size: float = 18,
    color: str = BBVA_DARK_TEXT,
    bold: bool = False,
    italic: bool = False,
    align=PP_ALIGN.LEFT,
    vertical_anchor=MSO_ANCHOR.TOP,
    font_name: str = BODY_FONT,
    auto_size: bool = False,
    margin: float = 0.02,
) -> None:
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(margin)
    tf.margin_right = Inches(margin)
    tf.margin_top = Inches(0.01)
    tf.margin_bottom = Inches(0.01)
    tf.vertical_anchor = vertical_anchor
    if auto_size:
        tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE

    p = tf.paragraphs[0]
    p.alignment = align
    p.space_after = Pt(0)
    run = p.add_run()
    run.text = text
    _set_font(run, font_name, font_size, color, bold=bold, italic=italic)


def _add_round_rect(
    slide,
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str,
    line: str | None = None,
) -> Any:
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill)
    shape.line.color.rgb = _rgb(line or fill)
    shape.line.width = Pt(0.75)
    return shape


def _add_separator(slide, x: float, y: float, w: float, color: str, height: float = 0.014) -> None:
    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(height))
    line.fill.solid()
    line.fill.fore_color.rgb = _rgb(color)
    line.line.color.rgb = _rgb(color)


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _sentence_safe_clip(value: Any, max_chars: int) -> str:
    """Clip text without leaving visible ellipsis or half-finished endings."""
    text = _normalize_text(value)
    if len(text) <= max_chars:
        return text

    sentences = re.split(r"(?<=[.!?])\s+", text)
    kept: list[str] = []
    size = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        candidate_size = size + len(sentence) + (1 if kept else 0)
        if candidate_size <= max_chars:
            kept.append(sentence)
            size = candidate_size
        else:
            break

    if kept:
        return " ".join(kept).strip()

    # Fallback for texts with no punctuation: cut on word boundary and close with a period.
    clipped = text[:max_chars].rsplit(" ", 1)[0].strip()
    if clipped and clipped[-1] not in ".!?":
        clipped += "."
    return clipped


def _clean_text(value: Any, limit: int | None = None, sentence_safe: bool = True) -> str:
    text = _normalize_text(value)
    if not limit or len(text) <= limit:
        return text
    if sentence_safe:
        return _sentence_safe_clip(text, limit)
    clipped = text[:limit].rsplit(" ", 1)[0].strip()
    if clipped and clipped[-1] not in ".!?:;":
        clipped += "."
    return clipped


def _limited_list(value: Any, limit: int, max_items: int) -> list[str]:
    if not isinstance(value, list):
        value = [value] if value else []
    return [_clean_text(item, limit, sentence_safe=True) for item in value if str(item).strip()][:max_items]


def _font_size_for_text(text: str, base: float, compact: float, dense: float, very_dense: float) -> float:
    n = len(_normalize_text(text))
    if n > 760:
        return very_dense
    if n > 620:
        return dense
    if n > 460:
        return compact
    return base


def _add_section_title(slide, title: str, x: float, y: float, w: float, color: str = BBVA_BLUE) -> None:
    _add_textbox(slide, title, x, y, w, 0.28, font_size=11.2, color=color, bold=True, font_name=BODY_FONT)


def _add_card(
    slide,
    title: str,
    body: str | list[str],
    x: float,
    y: float,
    w: float,
    h: float,
    fill: str = BBVA_WHITE,
    accent: str = BBVA_BLUE,
    body_size: float = 8.8,
    max_bullets: int = 3,
    max_chars: int = 115,
    body_limit: int | None = None,
    dense_body_size: tuple[float, float, float, float] | None = None,
) -> None:
    _add_round_rect(slide, x, y, w, h, fill=fill, line=fill)

    title_color = BBVA_BLUE if fill != BBVA_BLUE else BBVA_WHITE
    body_color = BBVA_DARK_TEXT if fill != BBVA_BLUE else BBVA_WHITE

    _add_section_title(slide, title, x + 0.26, y + 0.18, w - 0.52, color=title_color)
    _add_separator(slide, x + 0.26, y + 0.56, w - 0.52, accent, height=0.014)

    text_shape = slide.shapes.add_textbox(Inches(x + 0.28), Inches(y + 0.72), Inches(w - 0.56), Inches(h - 0.86))
    tf = text_shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    tf.margin_left = Inches(0.00)
    tf.margin_right = Inches(0.00)
    tf.margin_top = Inches(0.00)
    tf.margin_bottom = Inches(0.00)

    if isinstance(body, list):
        bullets = _limited_list(body, max_chars, max_bullets)
        for idx, bullet in enumerate(bullets):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            p.space_after = Pt(3)
            p.line_spacing = 1.03
            run = p.add_run()
            run.text = "• " + bullet
            _set_font(run, BODY_FONT, body_size, body_color)
        return

    text = _clean_text(body, body_limit, sentence_safe=True)
    dynamic_body_size = body_size
    if dense_body_size is not None:
        dynamic_body_size = _font_size_for_text(text, *dense_body_size)

    p = tf.paragraphs[0]
    p.space_after = Pt(1)
    p.line_spacing = 1.00
    run = p.add_run()
    run.text = text
    _set_font(run, BODY_FONT, dynamic_body_size, body_color)


def _add_risk_badge(slide, risk_level: str, x: float, y: float) -> None:
    risk = (risk_level or "medio").lower().strip()
    label = {"alto": "Riesgo alto", "medio": "Riesgo medio", "bajo": "Riesgo bajo"}.get(risk, "Riesgo medio")
    color = {"alto": BBVA_MANDARIN, "medio": BBVA_SERENE_BLUE, "bajo": BBVA_LIME}.get(risk, BBVA_SERENE_BLUE)
    _add_round_rect(slide, x, y, 1.38, 0.36, fill=color, line=color)
    _add_textbox(
        slide,
        label,
        x + 0.06,
        y + 0.065,
        1.26,
        0.20,
        font_size=8.5,
        color=BBVA_MIDNIGHT,
        bold=True,
        align=PP_ALIGN.CENTER,
        vertical_anchor=MSO_ANCHOR.MIDDLE,
    )


def _period_label(report: dict[str, Any]) -> str:
    period = report.get("period", {}) if isinstance(report.get("period"), dict) else {}
    return str(period.get("label") or "Período quincenal")


def _add_header(slide, title: str, section: str, period_label: str) -> None:
    _add_logo(slide, "blue", 11.72, 0.32, 0.88)
    _add_textbox(slide, "INFORME QUINCENAL / ASUNTOS PÚBLICOS", 0.55, 0.31, 3.4, 0.20, font_size=6.7, color=BBVA_BLUE, bold=True)
    _add_textbox(slide, section.upper(), 4.15, 0.31, 3.3, 0.20, font_size=6.7, color=BBVA_BLUE, bold=True)
    _add_textbox(slide, title, 0.55, 0.72, 7.6, 0.56, font_size=25.5, color=BBVA_BLUE, bold=True, font_name=TITLE_FONT, auto_size=True)
    _add_textbox(slide, period_label, 0.56, 1.18, 5.0, 0.22, font_size=8.5, color=BBVA_GREY_4)


def _add_page_number(slide, page: int) -> None:
    _add_textbox(slide, f"p. {page}", 12.35, 7.05, 0.45, 0.18, font_size=7.2, color=BBVA_BLUE, align=PP_ALIGN.RIGHT)


def _add_cover_micro_fallback(slide) -> None:
    _add_round_rect(slide, 8.30, 2.05, 0.72, 2.72, fill=BBVA_SERENE_BLUE, line=BBVA_SERENE_BLUE)
    _add_round_rect(slide, 9.18, 1.55, 0.72, 3.22, fill=BBVA_ICE, line=BBVA_ICE)
    _add_round_rect(slide, 10.06, 2.55, 0.72, 2.22, fill=BBVA_SERENE_BLUE, line=BBVA_SERENE_BLUE)
    circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(9.15), Inches(4.92), Inches(0.78), Inches(0.78))
    circle.fill.solid()
    circle.fill.fore_color.rgb = _rgb(BBVA_PURPLE)
    circle.line.color.rgb = _rgb(BBVA_PURPLE)


def _add_cover_icon(slide) -> None:
    if EMOJI_POLITICO.exists():
        slide.shapes.add_picture(str(EMOJI_POLITICO), Inches(9.45), Inches(0.52), width=Inches(2.35))
    else:
        _add_cover_micro_fallback(slide)


def _add_cover(slide, period_label: str) -> None:
    _set_background(slide, BBVA_BLUE)
    _add_logo(slide, "white", 0.55, 0.42, 1.05)
    _add_cover_icon(slide)

    _add_textbox(slide, period_label, 0.58, 3.42, 4.8, 0.22, font_size=10.2, color=BBVA_WHITE)
    _add_textbox(slide, "Dirección de Relaciones Institucionales", 0.58, 3.68, 5.9, 0.25, font_size=10.2, color=BBVA_WHITE)
    _add_separator(slide, 0.58, 4.08, 12.15, BBVA_WHITE, height=0.010)

    _add_textbox(
        slide,
        "Contexto político\ny regulatorio",
        0.55,
        4.62,
        8.7,
        1.55,
        font_size=45,
        color=BBVA_WHITE,
        bold=True,
        font_name=TITLE_FONT,
        auto_size=True,
        margin=0.00,
    )
    _add_textbox(slide, "Informe quincenal · borrador editable", 0.58, 6.92, 5.6, 0.22, font_size=8.0, color=BBVA_WHITE, italic=True)


def _add_analysis(slide, report: dict[str, Any]) -> None:
    analysis = report.get("analysis", {})
    period_label = _period_label(report)
    stats = report.get("stats", {}) if isinstance(report.get("stats"), dict) else {}
    generated_at = datetime.now().strftime("%d/%m/%Y")

    _set_background(slide, BBVA_SAND)
    _add_header(slide, "Análisis ejecutivo", "Contexto político y regulatorio", period_label)

    headline = _clean_text(analysis.get("headline") or "Contexto político quincenal", TEXT_LIMITS["headline"], sentence_safe=False)
    _add_textbox(slide, headline, 0.56, 1.46, 9.35, 0.34, font_size=14.6, color=BBVA_DARK_TEXT, bold=True, auto_size=True)
    _add_risk_badge(slide, analysis.get("risk_level", "medio"), 10.45, 1.44)

    # Executive vision gets the full width to avoid unfinished text. The text is sentence-safe and auto-fits.
    _add_card(
        slide,
        "Visión ejecutiva",
        analysis.get("executive_vision", ""),
        0.55,
        1.88,
        12.20,
        2.24,
        fill=BBVA_WHITE,
        accent=BBVA_SERENE_BLUE,
        body_size=8.9,
        body_limit=TEXT_LIMITS["executive_vision"],
        dense_body_size=(8.9, 8.2, 7.6, 7.1),
    )

    _add_card(
        slide,
        "Principales hitos",
        analysis.get("key_developments", []),
        0.55,
        4.38,
        3.90,
        2.05,
        fill=BBVA_WHITE,
        accent=BBVA_BLUE,
        body_size=7.35,
        max_bullets=3,
        max_chars=TEXT_LIMITS["key_developments"],
    )
    _add_card(
        slide,
        "Implicancias para BBVA / sistema financiero",
        analysis.get("bbva_implications", []),
        4.72,
        4.38,
        4.05,
        2.05,
        fill=BBVA_SERENE_BLUE,
        accent=BBVA_BLUE,
        body_size=7.25,
        max_bullets=2,
        max_chars=TEXT_LIMITS["bbva_implications"],
    )
    _add_card(
        slide,
        "Focos a monitorear",
        analysis.get("watchlist", []),
        9.04,
        4.38,
        3.71,
        2.05,
        fill=BBVA_WHITE,
        accent=BBVA_LIME,
        body_size=7.05,
        max_bullets=3,
        max_chars=TEXT_LIMITS["watchlist"],
    )

    footer = (
        f"Fuentes relevadas: {stats.get('raw_news_count', 0)} | "
        f"Noticias seleccionadas: {stats.get('selected_news_count', 0)} | "
        f"Generado: {generated_at}"
    )
    _add_textbox(slide, footer, 0.55, 6.93, 9.7, 0.18, font_size=7.2, color=BBVA_GREY_4)
    _add_page_number(slide, 2)


def _add_closing(slide) -> None:
    _set_background(slide, BBVA_BLUE)
    # Smaller logo avoids pixelation from the source PNG while preserving brand hierarchy.
    _add_logo(slide, "white", 5.78, 3.18, 1.78)
    _add_textbox(
        slide,
        "Dirección de Relaciones Institucionales",
        0.65,
        6.90,
        12.0,
        0.22,
        font_size=8.4,
        color=BBVA_WHITE,
        align=PP_ALIGN.CENTER,
    )


def create_aapp_pptx(report: dict[str, Any], output_path: Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    period_label = _period_label(report)

    prs = Presentation()
    prs.slide_width = Inches(SLIDE_W)
    prs.slide_height = Inches(SLIDE_H)
    blank = prs.slide_layouts[6]

    slide = prs.slides.add_slide(blank)
    _add_cover(slide, period_label)

    slide = prs.slides.add_slide(blank)
    _add_analysis(slide, report)

    slide = prs.slides.add_slide(blank)
    _add_closing(slide)

    prs.save(str(output_path))
    return output_path
