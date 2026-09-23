import unittest

from src.enrichment.date_extraction import extract_html_date_signals


class DateExtractionTests(unittest.TestCase):
    def test_jsonld_date_published_is_usable(self):
        html = """
        <script type="application/ld+json">
          {"@type":"Article","datePublished":"2026-08-14","dateModified":"2026-09-01"}
        </script>
        """
        signals = extract_html_date_signals(html, "https://example.com/case")
        pub = [x for x in signals if x.kind == "jsonld_datePublished"]
        mod = [x for x in signals if x.kind == "jsonld_dateModified"]
        self.assertTrue(pub)
        self.assertEqual(pub[0].normalized_date, "2026-08-14")
        self.assertTrue(pub[0].usable_as_publication_date)
        self.assertTrue(mod)
        self.assertFalse(mod[0].usable_as_publication_date)

    def test_article_published_time_is_usable(self):
        html = '<meta property="article:published_time" content="2026-08-14T10:15:00+02:00">'
        signals = extract_html_date_signals(html, "https://example.com/case")
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].kind, "meta_article_published_time")
        self.assertEqual(signals[0].normalized_date, "2026-08-14")
        self.assertTrue(signals[0].usable_as_publication_date)

    def test_modified_time_is_not_publication_date(self):
        html = '<meta property="article:modified_time" content="2026-09-20">'
        signals = extract_html_date_signals(html, "https://example.com/case")
        self.assertEqual(len(signals), 1)
        self.assertEqual(signals[0].kind, "meta_last_modified")
        self.assertFalse(signals[0].usable_as_publication_date)


if __name__ == "__main__":
    unittest.main()
