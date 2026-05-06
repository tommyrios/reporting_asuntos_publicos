from __future__ import annotations

import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


import unittest

from scripts.google_docs_builder import _build_document_text


class DocsBuilderTests(unittest.TestCase):
    def test_builds_apuntes_format(self):
        report = {
            "title": "Apuntes políticos #7",
            "date_label": "1 de Mayo de 2026",
            "lead": "El oficialismo conserva capacidad de gestión del proceso político.",
            "developments": [
                {"headline": "El Congreso se consolidó como espacio de defensa política", "analysis": "La sesión marcó el principal hecho institucional de la quincena."}
            ],
            "prospective_keys": ["Evolución de la conflictividad social.", "Capacidad de control político en Congreso."],
        }
        built = _build_document_text(report)
        self.assertIn("BBVA", built.text)
        self.assertIn("NOTA INTERNA", built.text)
        self.assertIn("─ Claves prospectivas", built.text)
        self.assertNotIn("...", built.text)


if __name__ == "__main__":
    unittest.main()
