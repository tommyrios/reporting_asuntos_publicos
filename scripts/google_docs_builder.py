from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

from google_services import docs_service, drive_service
from utils import parse_bool, split_emails

logger = logging.getLogger(__name__)

ELECTRIC_BLUE = {"red": 0.0, "green": 0.0745, "blue": 0.5686}  # #001391
SERENE_BLUE = {"red": 0.5216, "green": 0.7843, "blue": 1.0}  # #85C8FF
GREY_5 = {"red": 0.0, "green": 0.0196, "blue": 0.098}  # #000519
WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
RED_NOTE = {"red": 0.91, "green": 0.0, "blue": 0.05}
SAND = {"red": 0.9686, "green": 0.9725, "blue": 0.9725}


def _color(rgb: dict[str, float]) -> dict[str, Any]:
    return {"color": {"rgbColor": rgb}}


def _pt(value: float) -> dict[str, Any]:
    return {"magnitude": value, "unit": "PT"}


@dataclass
class Segment:
    name: str
    start: int
    end: int
    text: str


class TextBuilder:
    def __init__(self) -> None:
        self.text = ""
        self.index = 1  # Google Docs body starts at index 1.
        self.segments: dict[str, Segment] = {}
        self.multi: dict[str, list[Segment]] = {}

    def add(self, name: str, value: str, multi: bool = False) -> Segment:
        start = self.index + len(self.text)
        self.text += value
        end = start + len(value)
        segment = Segment(name, start, end, value)
        if multi:
            self.multi.setdefault(name, []).append(segment)
        else:
            self.segments[name] = segment
        return segment


def _text_style_request(segment: Segment, style: dict[str, Any], fields: str) -> dict[str, Any]:
    return {
        "updateTextStyle": {
            "range": {"startIndex": segment.start, "endIndex": segment.end},
            "textStyle": style,
            "fields": fields,
        }
    }


def _paragraph_style_request(segment: Segment, style: dict[str, Any], fields: str) -> dict[str, Any]:
    return {
        "updateParagraphStyle": {
            "range": {"startIndex": segment.start, "endIndex": segment.end},
            "paragraphStyle": style,
            "fields": fields,
        }
    }


def _font(family: str, size: float, bold: bool | None = None, color: dict[str, float] | None = None, italic: bool | None = None) -> tuple[dict[str, Any], str]:
    style: dict[str, Any] = {
        "weightedFontFamily": {"fontFamily": family},
        "fontSize": _pt(size),
    }
    fields = ["weightedFontFamily", "fontSize"]
    if bold is not None:
        style["bold"] = bold
        fields.append("bold")
    if italic is not None:
        style["italic"] = italic
        fields.append("italic")
    if color is not None:
        style["foregroundColor"] = _color(color)
        fields.append("foregroundColor")
    return style, ",".join(fields)


def _build_document_text(report: dict[str, Any]) -> TextBuilder:
    b = TextBuilder()
    b.add("brand_bar", "BBVA\n")
    b.add("spacer_1", "\n")
    meta = "DIRECCIÓN DE RELACIONES INSTITUCIONALES"
    note = os.getenv("REPORT_INTERNAL_LABEL", "NOTA INTERNA")
    b.add("meta_line", f"{meta}                                      {note}\n")
    # Track the right-side note within the metadata line.
    meta_segment = b.segments["meta_line"]
    note_start = meta_segment.start + meta_segment.text.rfind(note)
    b.segments["note_internal"] = Segment("note_internal", note_start, note_start + len(note), note)
    b.add("title", f"{report['title']}\n")
    b.add("date", f"{report['date_label']}\n")
    b.add("spacer_2", "\n")
    b.add("lead", f"{report['lead']}\n")
    b.add("spacer_3", "\n")

    for item in report.get("developments", []):
        prefix = "─ "
        headline = str(item.get("headline", "")).strip()
        analysis = str(item.get("analysis", "")).strip()
        sentence_end = "." if not headline.endswith((".", "?", "!")) else ""
        full = f"{prefix}{headline}{sentence_end} {analysis}\n\n"
        seg = b.add("development", full, multi=True)
        headline_start = seg.start + len(prefix)
        headline_end = headline_start + len(headline) + len(sentence_end)
        b.multi.setdefault("development_headline", []).append(Segment("development_headline", headline_start, headline_end, headline + sentence_end))

    b.add("keys_heading", "─ Claves prospectivas\n")
    for key in report.get("prospective_keys", []):
        b.add("key", f"   ○ {key}\n", multi=True)
    b.add("spacer_4", "\n")
    b.add("thanks", "Gracias!\n")
    b.add("footer", "DIRECCIÓN DE RELACIONES INSTITUCIONALES\n")
    return b


def _build_style_requests(builder: TextBuilder) -> list[dict[str, Any]]:
    requests: list[dict[str, Any]] = []
    if builder.text:
        all_segment = Segment("all", 1, 1 + len(builder.text), builder.text)
        style, fields = _font("Lato", 10.5, bold=False, color=GREY_5)
        requests.append(_text_style_request(all_segment, style, fields))
        requests.append(
            {
                "updateDocumentStyle": {
                    "documentStyle": {
                        "marginTop": _pt(48),
                        "marginBottom": _pt(42),
                        "marginLeft": _pt(54),
                        "marginRight": _pt(54),
                    },
                    "fields": "marginTop,marginBottom,marginLeft,marginRight",
                }
            }
        )

    # Brand blue bar.
    bar = builder.segments["brand_bar"]
    style, fields = _font("Lato", 17, bold=True, color=WHITE)
    requests.append(_text_style_request(bar, style, fields))
    requests.append(
        _paragraph_style_request(
            bar,
            {
                "shading": {"backgroundColor": _color(ELECTRIC_BLUE)},
                "spaceAbove": _pt(8),
                "spaceBelow": _pt(8),
                "indentStart": _pt(18),
            },
            "shading,spaceAbove,spaceBelow,indentStart",
        )
    )

    meta = builder.segments["meta_line"]
    style, fields = _font("Lato", 7.5, bold=True, color=ELECTRIC_BLUE)
    requests.append(_text_style_request(meta, style, fields))
    note = builder.segments["note_internal"]
    style, fields = _font("Lato", 9.5, bold=True, color=RED_NOTE)
    requests.append(_text_style_request(note, style, fields))

    title = builder.segments["title"]
    style, fields = _font("Source Serif 4", 27, bold=True, color=ELECTRIC_BLUE)
    requests.append(_text_style_request(title, style, fields))
    requests.append(_paragraph_style_request(title, {"spaceAbove": _pt(10), "spaceBelow": _pt(2)}, "spaceAbove,spaceBelow"))

    date = builder.segments["date"]
    style, fields = _font("Lato", 10.5, bold=False, color=GREY_5)
    requests.append(_text_style_request(date, style, fields))

    lead = builder.segments["lead"]
    style, fields = _font("Source Serif 4", 12.5, bold=True, color=ELECTRIC_BLUE)
    requests.append(_text_style_request(lead, style, fields))
    requests.append(_paragraph_style_request(lead, {"spaceAbove": _pt(12), "spaceBelow": _pt(12), "lineSpacing": 94}, "spaceAbove,spaceBelow,lineSpacing"))

    for seg in builder.multi.get("development", []):
        requests.append(
            _paragraph_style_request(
                seg,
                {
                    "spaceAbove": _pt(4),
                    "spaceBelow": _pt(8),
                    "lineSpacing": 105,
                    "indentStart": _pt(0),
                },
                "spaceAbove,spaceBelow,lineSpacing,indentStart",
            )
        )
    for seg in builder.multi.get("development_headline", []):
        style, fields = _font("Lato", 10.5, bold=True, color=ELECTRIC_BLUE)
        requests.append(_text_style_request(seg, style, fields))

    keys_heading = builder.segments["keys_heading"]
    style, fields = _font("Lato", 10.5, bold=True, color=ELECTRIC_BLUE)
    requests.append(_text_style_request(keys_heading, style, fields))
    requests.append(
        _paragraph_style_request(
            keys_heading,
            {"spaceAbove": _pt(10), "spaceBelow": _pt(4), "indentStart": _pt(0)},
            "spaceAbove,spaceBelow,indentStart",
        )
    )
    for seg in builder.multi.get("key", []):
        style, fields = _font("Lato", 10, bold=True, color=ELECTRIC_BLUE)
        requests.append(_text_style_request(seg, style, fields))
        requests.append(_paragraph_style_request(seg, {"spaceBelow": _pt(1), "lineSpacing": 95}, "spaceBelow,lineSpacing"))

    thanks = builder.segments["thanks"]
    footer = builder.segments["footer"]
    footer_block = Segment("footer_block", thanks.start, footer.end, builder.text[thanks.start - 1 : footer.end - 1])
    requests.append(
        _paragraph_style_request(
            footer_block,
            {"shading": {"backgroundColor": _color(SERENE_BLUE)}, "alignment": "CENTER", "spaceAbove": _pt(8), "spaceBelow": _pt(4)},
            "shading,alignment,spaceAbove,spaceBelow",
        )
    )
    style, fields = _font("Lato", 11, bold=True, color=WHITE)
    requests.append(_text_style_request(thanks, style, fields))
    style, fields = _font("Lato", 7, bold=True, color=ELECTRIC_BLUE)
    requests.append(_text_style_request(footer, style, fields))
    return requests


def create_google_doc(report: dict[str, Any], report_id: str) -> dict[str, str]:
    title = f"{report['title']} - {report.get('date_label', '')}".strip(" -")
    docs = docs_service()
    drive = drive_service()
    doc = docs.documents().create(body={"title": title}).execute()
    doc_id = doc["documentId"]

    builder = _build_document_text(report)
    requests = [{"insertText": {"location": {"index": 1}, "text": builder.text}}]
    requests.extend(_build_style_requests(builder))
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()

    folder_id = os.getenv("GOOGLE_DOCS_FOLDER_ID", "").strip()
    if folder_id:
        drive.files().update(fileId=doc_id, addParents=folder_id, fields="id,parents,webViewLink", supportsAllDrives=True).execute()

    share_with = split_emails(os.getenv("GOOGLE_DOCS_SHARE_WITH", ""))
    role = os.getenv("GOOGLE_DOCS_SHARE_ROLE", "writer").strip() or "writer"
    for email in share_with:
        drive.permissions().create(
            fileId=doc_id,
            body={"type": "user", "role": role, "emailAddress": email},
            sendNotificationEmail=False,
            supportsAllDrives=True,
        ).execute()

    if parse_bool(os.getenv("GOOGLE_DOCS_ANYONE_WITH_LINK"), False):
        drive.permissions().create(
            fileId=doc_id,
            body={"type": "anyone", "role": "reader"},
            sendNotificationEmail=False,
            supportsAllDrives=True,
        ).execute()

    # Validate through Docs API and retrieve Drive web link.
    docs.documents().get(documentId=doc_id, fields="documentId,title").execute()
    meta = drive.files().get(fileId=doc_id, fields="id,name,webViewLink", supportsAllDrives=True).execute()
    return {"document_id": doc_id, "document_url": meta.get("webViewLink") or f"https://docs.google.com/document/d/{doc_id}/edit", "name": meta.get("name", title)}
