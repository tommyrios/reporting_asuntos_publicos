from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

from config import BBVA_BLUE, BBVA_DARK_TEXT, BBVA_LIGHT_BLUE, BBVA_MEDIUM_BLUE, BRAND_DIR
from utils import truncate

LOGO_BLUE = BRAND_DIR / "bbva_logo_blue.png"
LOGO_WHITE = BRAND_DIR / "bbva_logo_white.png"


def _rgb(hex_color: str) -> RGBColor:
    return RGBColor.from_string(hex_color.replace("#", ""))


def _set_background(slide, hex_color: str) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = _rgb(hex_color)


def _add_logo(slide, color: str, x: float, y: float, width: float) -> None:
    logo = LOGO_WHITE if color == "white" else LOGO_BLUE
    if logo.exists():
        slide.shapes.add_picture(str(logo), Inches(x), Inches(y), width=Inches(width))
    else:
        tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(width), Inches(0.35))
        p = tb.text_frame.paragraphs[0]
        p.text = "BBVA"
        p.font.bold = True
        p.font.size = Pt(22)
        p.font.color.rgb = _rgb("FFFFFF" if color == "white" else BBVA_BLUE)


def _add_textbox(
    slide,
    text: str,
    x: float,
    y: float,
    w: float,
    h: float,
    font_size: int = 18,
    color: str = BBVA_DARK_TEXT,
    bold: bool = False,
    align=PP_ALIGN.LEFT,
    vertical_anchor=MSO_ANCHOR.TOP,
) -> None:
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear()
    tf.margin_left = Inches(0.03)
    tf.margin_right = Inches(0.03)
    tf.margin_top = Inches(0.02)
    tf.vertical_anchor = vertical_anchor
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = _rgb(color)


def _add_card(slide, title: str, body: str | list[str], x: float, y: float, w: float, h: float, title_color: str = BBVA_BLUE) -> None:
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb("F4F7F9")
    shape.line.color.rgb = _rgb("D8E1E8")
    shape.line.width = Pt(1)

    _add_textbox(slide, title, x + 0.18, y + 0.12, w - 0.36, 0.32, font_size=12, color=title_color, bold=True)
    text_shape = slide.shapes.add_textbox(Inches(x + 0.18), Inches(y + 0.52), Inches(w - 0.36), Inches(h - 0.65))
    tf = text_shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = Inches(0.02)
    tf.margin_right = Inches(0.02)
    tf.margin_top = Inches(0.01)

    if isinstance(body, list):
        bullets = body[:4]
        for idx, bullet in enumerate(bullets):
            p = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
            p.text = "• " + truncate(str(bullet), 155)
            p.font.size = Pt(10.5)
            p.font.color.rgb = _rgb(BBVA_DARK_TEXT)
            p.space_after = Pt(5)
    else:
        p = tf.paragraphs[0]
        p.text = truncate(str(body), 650)
        p.font.size = Pt(11)
        p.font.color.rgb = _rgb(BBVA_DARK_TEXT)
        p.space_after = Pt(4)


def _add_risk_badge(slide, risk_level: str) -> None:
    risk = (risk_level or "medio").lower().strip()
    label = {"alto": "Riesgo alto", "medio": "Riesgo medio", "bajo": "Riesgo bajo"}.get(risk, "Riesgo medio")
    color = {"alto": "B92B27", "medio": BBVA_MEDIUM_BLUE, "bajo": "277A3E"}.get(risk, BBVA_MEDIUM_BLUE)
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(10.55), Inches(0.65), Inches(1.55), Inches(0.38))
    shape.fill.solid()
    shape.fill.fore_color.rgb = _rgb(color)
    shape.line.color.rgb = _rgb(color)
    tf = shape.text_frame
    tf.clear()
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    p.text = label
    p.font.size = Pt(10)
    p.font.bold = True
    p.font.color.rgb = _rgb("FFFFFF")


def _period_label(report: dict[str, Any]) -> str:
    period = report.get("period", {}) if isinstance(report.get("period"), dict) else {}
    return str(period.get("label") or "Período quincenal")


def create_aapp_pptx(report: dict[str, Any], output_path: Path) -> Path:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    analysis = report.get("analysis", {})
    period_label = _period_label(report)
    generated_at = datetime.now().strftime("%d/%m/%Y")

    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    # Slide 1: portada
    slide = prs.slides.add_slide(blank)
    _set_background(slide, BBVA_BLUE)
    _add_logo(slide, "white", 5.35, 2.25, 2.6)
    _add_textbox(slide, "Informe quincenal", 1.05, 4.15, 11.2, 0.45, font_size=23, color="FFFFFF", bold=True, align=PP_ALIGN.CENTER)
    _add_textbox(slide, "Contexto político y regulatorio", 1.05, 4.65, 11.2, 0.45, font_size=20, color="FFFFFF", align=PP_ALIGN.CENTER)
    _add_textbox(slide, period_label, 1.05, 5.24, 11.2, 0.35, font_size=13, color=BBVA_LIGHT_BLUE, align=PP_ALIGN.CENTER)
    _add_textbox(slide, "Dirección de Relaciones Institucionales", 1.05, 6.78, 11.2, 0.28, font_size=10, color="FFFFFF", align=PP_ALIGN.CENTER)

    # Slide 2: análisis
    slide = prs.slides.add_slide(blank)
    _set_background(slide, "FFFFFF")
    _add_logo(slide, "blue", 11.05, 0.35, 1.35)
    _add_textbox(slide, "Análisis ejecutivo", 0.65, 0.42, 6.7, 0.42, font_size=21, color=BBVA_BLUE, bold=True)
    _add_textbox(slide, period_label, 0.65, 0.86, 7.4, 0.28, font_size=10.5, color="666666")
    _add_risk_badge(slide, analysis.get("risk_level", "medio"))

    headline = analysis.get("headline") or "Contexto político quincenal"
    _add_textbox(slide, headline, 0.65, 1.25, 12.0, 0.42, font_size=17, color=BBVA_DARK_TEXT, bold=True)

    _add_card(slide, "Visión ejecutiva", analysis.get("executive_vision", ""), 0.65, 1.86, 5.95, 2.35)
    _add_card(slide, "Principales hitos", analysis.get("key_developments", []), 6.85, 1.86, 5.85, 2.35)
    _add_card(slide, "Implicancias para BBVA / sistema financiero", analysis.get("bbva_implications", []), 0.65, 4.42, 5.95, 1.65)
    _add_card(slide, "Focos a monitorear", analysis.get("watchlist", []), 6.85, 4.42, 5.85, 1.65)

    stats = report.get("stats", {}) if isinstance(report.get("stats"), dict) else {}
    footer = f"Fuentes relevadas: {stats.get('raw_news_count', 0)} · Noticias seleccionadas: {stats.get('selected_news_count', 0)} · Generado: {generated_at}"
    _add_textbox(slide, footer, 0.65, 6.95, 11.8, 0.22, font_size=8.5, color="777777")

    # Slide 3: contraportada
    slide = prs.slides.add_slide(blank)
    _set_background(slide, BBVA_BLUE)
    _add_logo(slide, "white", 5.35, 3.32, 2.6)

    prs.save(str(output_path))
    return output_path
