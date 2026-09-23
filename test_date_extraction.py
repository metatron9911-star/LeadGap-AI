from src.enrichment.date_extraction import extract_html_date_signals


def test_jsonld_date_published_is_usable():
    html = """
    <script type="application/ld+json">
      {"@type":"Article","datePublished":"2026-08-14","dateModified":"2026-09-01"}
    </script>
    """
    signals = extract_html_date_signals(html, "https://example.com/case")
    pub = [x for x in signals if x.kind == "jsonld_datePublished"]
    mod = [x for x in signals if x.kind == "jsonld_dateModified"]
    assert pub and pub[0].normalized_date == "2026-08-14"
    assert pub[0].usable_as_publication_date is True
    assert mod and mod[0].usable_as_publication_date is False


def test_article_published_time_is_usable():
    html = '<meta property="article:published_time" content="2026-08-14T10:15:00+02:00">'
    signals = extract_html_date_signals(html, "https://example.com/case")
    assert len(signals) == 1
    assert signals[0].kind == "meta_article_published_time"
    assert signals[0].normalized_date == "2026-08-14"
    assert signals[0].usable_as_publication_date is True


def test_modified_time_is_not_publication_date():
    html = '<meta property="article:modified_time" content="2026-09-20">'
    signals = extract_html_date_signals(html, "https://example.com/case")
    assert len(signals) == 1
    assert signals[0].kind == "meta_last_modified"
    assert signals[0].usable_as_publication_date is False
