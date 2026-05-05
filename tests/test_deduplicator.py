import sys
import unittest
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1] / "scripts"))

from deduplicator import deduplicate_news
from news_models import NewsItem


class DeduplicatorTest(unittest.TestCase):
    def test_deduplicates_same_url(self):
        items = [
            NewsItem(title="BCRA anuncia cambios regulatorios", url="https://example.com/a?utm_source=x"),
            NewsItem(title="BCRA anuncia cambios regulatorios", url="https://example.com/a"),
        ]
        unique, duplicates = deduplicate_news(items)
        self.assertEqual(len(unique), 1)
        self.assertEqual(len(duplicates), 1)

    def test_keeps_distinct_titles(self):
        items = [
            NewsItem(title="El Congreso debate presupuesto", url="https://example.com/a"),
            NewsItem(title="Bancos siguen nuevas normas del BCRA", url="https://example.com/b"),
        ]
        unique, duplicates = deduplicate_news(items)
        self.assertEqual(len(unique), 2)
        self.assertEqual(len(duplicates), 0)


if __name__ == "__main__":
    unittest.main()
