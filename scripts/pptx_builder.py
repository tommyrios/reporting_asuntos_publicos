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
from utils import truncate

LOGO_BLUE = BRAND_DIR / "bbva_logo_blue.png"
LOGO_WHITE = BRAND_DIR / "bbva_logo_white.png"

SLIDE_W = 13.333
SLIDE_H = 7.5

TEXT_LIMITS = {
    "headline": 78,
    "executive_vision": 560,
    "key_developments": 118,
    "bbva_implications": 112,
    "watchlist": 105,
}


def _rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color.replace("#", ""))


def _set_background(slide, hex_color: str) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(hex_color)


def _set_font(run, font_name: str, size: float, color: str, bold: bool = False, italic: bool = False) -> None:
    run.font.name = font_name
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = _rgb(color)


def _add_logo(slide, color: str, x: float, y: float, width: float) -> None:
    logo = LOGO_WHITE if color == "white" else LOGO_BLUE
    if logo.exists():
        slide.shapes.add_picture(str(logo), Inches(x), Inches(y), width=Inches(width))
    else:
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
) -> None:
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.02)
    tf.margin_right = Inches(0.02)
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


def _add_round_rect(slide, x: float, y: float, w: float, h: float, fill: str, line: str | None = None) -> Any:
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(fill)
    shape.line.color.rgb = _rgb(line or fill)
    shape.line.width = Pt(0.75)
    return shape


def _clean_text(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return truncate(text, limit)


def _limited_list(value: Any, limit: int, max_items: int) -> list[str]:
    if not isinstance(value, list):
        value = [value] if value else []
    return [_clean_text(item, limit) for item in value if str(item).strip()][:max_items]


def _add_section_title(slide, title: str, x: float, y: float, w: float, color: str = BBVA_BLUE) -> None:
    _add_textbox(slide, title, x, y, w, 0.28, font_size=11.5, color=color, bold=True, font_name=BODY_FONT)


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
    body_size: float = 9.4,
    max_bullets: int = 3,
    max_chars: int = 110,
) -> None:
    _add_round_rect(slide, x, y, w, h, fill=fill, line=fill)
    _add_section_title(slide, title, x + 0.26, y + 0.20, w - 0.52, color=BBVA_BLUE if fill != BBVA_BLUE else BBVA_WHITE)

    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(x + 0.26), Inches(y + 0.58), Inches(w - 0.52), Inches(0.012))
    line.fill.solid()
    line.fill.fore_color.rgb = _rgb(accent)
    line.line.color.rgb = _rgb(accent)

    text_shape = slide.shapes.add_textbox(Inches(x + 0.28), Inches(y + 0.72), Inches(w - 0.56), Inches(h - 0.88))
    tf = text_shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    tf.margin_left = Inches(0.00)
    tf.margin_right = Inches(0.00)
    tf.margin_top = Inches(0.00)
    tf.margin_bottom = Inches(0.00)

    body_color = BBVA_DARK_TEXT if fill != BBVA_BLUE else BBVA_WHITE
    if isinstance(body, list):
        bullets = _limited_list(body, max_chars, max_bullets)
        for idx, bullet in enumerate(bullets):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = "\u2022 " + bullet
            _set_font(run, BODY_FONT, body_size, body_color)
            p.space_after = Pt(3.5)
            p.line_spacing = 1.05
    else:
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = _clean_text(body, TEXT_LIMITS["executive_vision"])
        _set_font(run, BODY_FONT, body_size, body_color)
        p.space_after = Pt(2)
        p.line_spacing = 1.05


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
    return str(period.get("label") or "Per\u00edodo quincenal")


def _add_header(slide, title: str, section: str, period_label: str) -> None:
    _add_logo(slide, "blue", 11.72, 0.32, 0.88)
    _add_textbox(slide, "INFORME QUINCENAL / ASUNTOS P\u00daBLICOS", 0.55, 0.31, 3.4, 0.20, font_size=6.7, color=BBVA_BLUE, bold=True)
    _add_textbox(slide, section.upper(), 4.15, 0.31, 3.3, 0.20, font_size=6.7, color=BBVA_BLUE, bold=True)
    _add_textbox(slide, title, 0.55, 0.74, 7.6, 0.58, font_size=26, color=BBVA_BLUE, bold=True, font_name=TITLE_FONT, auto_size=True)
    _add_textbox(slide, period_label, 0.56, 1.22, 5.0, 0.22, font_size=8.5, color=BBVA_GREY_4)


def _add_page_number(slide, page: int) -> None:
    _add_textbox(slide, f"p. {page}", 12.35, 7.05, 0.45, 0.18, font_size=7.2, color=BBVA_BLUE, align=PP_ALIGN.RIGHT)


def _add_cover_micro(slide) -> None:
    _add_round_rect(slide, 8.30, 2.05, 0.72, 2.72, fill=BBVA_SERENE_BLUE, line=BBVA_SERENE_BLUE)
    _add_round_rect(slide, 9.18, 1.55, 0.72, 3.22, fill=BBVA_ICE, line=BBVA_ICE)
    _add_round_rect(slide, 10.06, 2.55, 0.72, 2.22, fill=BBVA_SERENE_BLUE, line=BBVA_SERENE_BLUE)
    circle = slide.shapes.add_shape(MSO_SHAPE.OVAL, Inches(9.15), Inches(4.92), Inches(0.78), Inches(0.78))
    circle.fill.solid()
    circle.fill.fore_color.rgb = _rgb(BBVA_PURPLE)
    circle.line.color.rgb = _rgb(BBVA_PURPLE)


def _add_cover(slide, period_label: str) -> None:
    _set_background(slide, BBVA_BLUE)
    _add_logo(slide, "white", 0.55, 0.45, 1.05)
    _add_textbox(slide, "DIRECCI\u00d3N DE RELACIONES INSTITUCIONALES", 0.62, 1.72, 5.9, 0.25, font_size=10, color=BBVA_WHITE)
    _add_textbox(
        slide,
        "Informe quincenal\nContexto pol\u00edtico\ny regulatorio",
        0.58,
        2.18,
        6.95,
        2.60,
        font_size=38,
        color=BBVA_WHITE,
        bold=True,
        font_name=TITLE_FONT,
        auto_size=True,
    )
    _add_textbox(slide, period_label, 0.62, 5.52, 5.8, 0.30, font_size=14, color=BBVA_SERENE_BLUE)
    _add_textbox(slide, "Borrador editable para revisi\u00f3n interna", 0.62, 6.85, 5.6, 0.22, font_size=8.4, color=BBVA_WHITE, italic=True)
    _add_cover_micro(slide)


def _add_analysis(slide, report: dict[str, Any]) -> None:
    analysis = report.get("analysis", {})
    period_label = _period_label(report)
    stats = report.get("stats", {}) if isinstance(report.get("stats"), dict) else {}
    generated_at = datetime.now().strftime("%d/%m/%Y")

    _set_background(slide, BBVA_SAND)
    _add_header(slide, "An\u00e1lisis ejecutivo", "Contexto pol\u00edtico y regulatorio", period_label)

    headline = _clean_text(analysis.get("headline") or "Contexto pol\u00edtico quincenal", TEXT_LIMITS["headline"])
    _add_textbox(slide, headline, 0.56, 1.54, 9.0, 0.36, font_size=15.5, color=BBVA_DARK_TEXT, bold=True, auto_size=True)
    _add_risk_badge(slide, analysis.get("risk_level", "medio"), 10.15, 1.52)

    _add_card(
        slide,
        "Visi\u00f3n ejecutiva",
        analysis.get("executive_vision", ""),
        0.55,
        2.05,
        5.55,
        2.68,
        fill=BBVA_WHITE,
        accent=BBVA_SERENE_BLUE,
        body_size=9.35,
    )
    _add_card(
        slide,
        "Principales hitos",
        analysis.get("key_developments", []),
        6.35,
        2.05,
        6.43,
        2.68,
        fill=BBVA_WHITE,
        accent=BBVA_BLUE,
        body_size=8.9,
        max_bullets=3,
        max_chars=TEXT_LIMITS["key_developments"],
    )
    _add_card(
        slide,
        "Implicancias para BBVA / sistema financiero",
        analysis.get("bbva_implications", []),
        0.55,
        5.00,
        6.05,
        1.48,
        fill=BBVA_SERENE_BLUE,
        accent=BBVA_BLUE,
        body_size=8.2,
        max_bullets=2,
        max_chars=TEXT_LIMITS["bbva_implications"],
    )
    _add_card(
        slide,
        "Focos a monitorear",
        analysis.get("watchlist", []),
        6.85,
        5.00,
        5.93,
        1.48,
        fill=BBVA_WHITE,
        accent=BBVA_LIME,
        body_size=8.0,
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
    _add_logo(slide, "white", 5.34, 3.18, 2.60)
    _add_textbox(slide, "Direcci\u00f3n de Relaciones Institucionales", 0.65, 6.90, 12.0, 0.22, font_size=8.4, color=BBVA_WHITE, align=PP_ALIGN.CENTER)


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
