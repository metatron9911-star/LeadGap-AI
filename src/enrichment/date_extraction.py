from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup


STRONG_PUBLICATION_KINDS = {
    "meta_article_published_time",
    "meta_date_published",
    "jsonld_datePublished",
    "feed_pubDate",
    "feed_published",
}

DIAGNOSTIC_ONLY_KINDS = {
    "jsonld_dateCreated",
    "jsonld_dateModified",
    "meta_last_modified",
    "http_last_modified",
    "sitemap_lastmod",
    "feed_updated",
    "wayback_first_snapshot",
    "media_asset_filename_date",
}


@dataclass(frozen=True)
class DateSignal:
    kind: str
    raw: str
    normalized_date: str | None
    source_url: str
    confidence: str
    usable_as_publication_date: bool
    note: str = ""


def _norm_url(url: str) -> str:
    p = urlsplit(url.strip())
    path = p.path or "/"
    if path != "/" and path.endswith("/"):
        path = path[:-1]
    return urlunsplit((p.scheme.lower(), p.netloc.lower(), path, "", ""))


def _parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip()
    if not text:
        return None

    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except ValueError:
        pass

    try:
        return parsedate_to_datetime(text).date().isoformat()
    except (TypeError, ValueError, OverflowError):
        pass

    m = re.search(r"\b(20\d{2})[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b", text)
    if m:
        y, mo, d = map(int, m.groups())
        try:
            return datetime(y, mo, d).date().isoformat()
        except ValueError:
            return None

    return None


def _signal(
    *,
    kind: str,
    raw: str,
    source_url: str,
    confidence: str,
    usable: bool,
    note: str = "",
) -> DateSignal:
    return DateSignal(
        kind=kind,
        raw=raw,
        normalized_date=_parse_date(raw),
        source_url=source_url,
        confidence=confidence,
        usable_as_publication_date=usable,
        note=note,
    )


def _walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def extract_html_date_signals(html: str, source_url: str) -> list[DateSignal]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[DateSignal] = []

    meta_rules = [
        ("property", "article:published_time", "meta_article_published_time", True, "high"),
        ("name", "datePublished", "meta_date_published", True, "high"),
        ("itemprop", "datePublished", "meta_date_published", True, "high"),
        ("property", "article:modified_time", "meta_last_modified", False, "diagnostic"),
        ("name", "last-modified", "meta_last_modified", False, "diagnostic"),
    ]
    for attr, value, kind, usable, confidence in meta_rules:
        for tag in soup.find_all("meta", attrs={attr: re.compile(f"^{re.escape(value)}$", re.I)}):
            raw = tag.get("content")
            if raw:
                out.append(_signal(
                    kind=kind,
                    raw=raw,
                    source_url=source_url,
                    confidence=confidence,
                    usable=usable,
                    note="HTML metadata",
                ))

    for tag in soup.find_all("time"):
        raw = tag.get("datetime")
        itemprop = (tag.get("itemprop") or "").lower()
        if raw and itemprop == "datepublished":
            out.append(_signal(
                kind="meta_date_published",
                raw=raw,
                source_url=source_url,
                confidence="high",
                usable=True,
                note="<time itemprop=datePublished>",
            ))

    for script in soup.find_all("script", attrs={"type": re.compile("ld\\+json", re.I)}):
        text = script.string or script.get_text()
        if not text.strip():
            continue
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            continue
        for obj in _walk_json(data):
            for key, usable, confidence in (
                ("datePublished", True, "high"),
                ("dateCreated", False, "diagnostic"),
                ("dateModified", False, "diagnostic"),
            ):
                raw = obj.get(key)
                if isinstance(raw, str) and raw.strip():
                    out.append(_signal(
                        kind=f"jsonld_{key}",
                        raw=raw,
                        source_url=source_url,
                        confidence=confidence,
                        usable=usable,
                        note=f"JSON-LD {key}",
                    ))

    return out


async def _fetch_text(client: httpx.AsyncClient, url: str) -> tuple[str | None, httpx.Headers | None]:
    try:
        response = await client.get(url)
        response.raise_for_status()
        return response.text, response.headers
    except (httpx.HTTPError, ValueError):
        return None, None


async def discover_sitemaps(client: httpx.AsyncClient, target_url: str) -> list[str]:
    parts = urlsplit(target_url)
    origin = f"{parts.scheme}://{parts.netloc}"
    candidates: list[str] = []

    robots, _ = await _fetch_text(client, urljoin(origin, "/robots.txt"))
    if robots:
        for line in robots.splitlines():
            if line.lower().startswith("sitemap:"):
                url = line.split(":", 1)[1].strip()
                if url and url not in candidates:
                    candidates.append(url)

    for suffix in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"):
        url = urljoin(origin, suffix)
        if url not in candidates:
            candidates.append(url)
    return candidates


async def sitemap_signals(
    client: httpx.AsyncClient,
    target_url: str,
    *,
    max_sitemaps: int = 30,
) -> list[DateSignal]:
    target = _norm_url(target_url)
    queue = await discover_sitemaps(client, target_url)
    seen: set[str] = set()
    out: list[DateSignal] = []

    while queue and len(seen) < max_sitemaps:
        sitemap_url = queue.pop(0)
        if sitemap_url in seen:
            continue
        seen.add(sitemap_url)
        xml, _ = await _fetch_text(client, sitemap_url)
        if not xml:
            continue

        soup = BeautifulSoup(xml, "html.parser")
        for sm in soup.find_all("sitemap"):
            loc = sm.find("loc")
            if loc and loc.get_text(strip=True):
                child = loc.get_text(strip=True)
                if child not in seen and child not in queue:
                    queue.append(child)

        for node in soup.find_all("url"):
            loc = node.find("loc")
            if not loc:
                continue
            loc_text = loc.get_text(strip=True)
            if _norm_url(loc_text) != target:
                continue
            lastmod = node.find("lastmod")
            if lastmod and lastmod.get_text(strip=True):
                out.append(_signal(
                    kind="sitemap_lastmod",
                    raw=lastmod.get_text(strip=True),
                    source_url=sitemap_url,
                    confidence="diagnostic",
                    usable=False,
                    note="Sitemap lastmod is modification metadata, not publication proof.",
                ))
    return out


def _feed_links_from_html(html: str, page_url: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    out: list[str] = []
    for link in soup.find_all("link", attrs={"rel": True, "href": True}):
        rel = " ".join(link.get("rel") or []).lower()
        typ = (link.get("type") or "").lower()
        if "alternate" in rel and ("rss" in typ or "atom" in typ or "feed" in typ):
            url = urljoin(page_url, link["href"])
            if url not in out:
                out.append(url)
    origin = f"{urlsplit(page_url).scheme}://{urlsplit(page_url).netloc}"
    for suffix in ("/feed/", "/feed", "/rss.xml", "/atom.xml"):
        url = urljoin(origin, suffix)
        if url not in out:
            out.append(url)
    return out


async def feed_signals(
    client: httpx.AsyncClient,
    target_url: str,
    html: str,
) -> list[DateSignal]:
    target = _norm_url(target_url)
    out: list[DateSignal] = []
    for feed_url in _feed_links_from_html(html, target_url)[:10]:
        xml, _ = await _fetch_text(client, feed_url)
        if not xml:
            continue
        soup = BeautifulSoup(xml, "html.parser")
        for entry in soup.find_all(["item", "entry"]):
            links: list[str] = []
            link_text = entry.find("link")
            if link_text:
                href = link_text.get("href")
                if href:
                    links.append(href)
                text = link_text.get_text(strip=True)
                if text.startswith("http"):
                    links.append(text)
            guid = entry.find("guid")
            if guid:
                g = guid.get_text(strip=True)
                if g.startswith("http"):
                    links.append(g)
            if target not in {_norm_url(x) for x in links}:
                continue

            for tag_name, kind, usable, confidence in (
                ("pubDate", "feed_pubDate", True, "high"),
                ("published", "feed_published", True, "high"),
                ("updated", "feed_updated", False, "diagnostic"),
            ):
                tag = entry.find(tag_name)
                if tag and tag.get_text(strip=True):
                    out.append(_signal(
                        kind=kind,
                        raw=tag.get_text(strip=True),
                        source_url=feed_url,
                        confidence=confidence,
                        usable=usable,
                        note="Exact canonical/entry URL match required.",
                    ))
    return out


async def wayback_signal(client: httpx.AsyncClient, target_url: str) -> list[DateSignal]:
    endpoint = "https://web.archive.org/cdx/search/cdx"
    params = {
        "url": target_url,
        "output": "json",
        "filter": "statuscode:200",
        "fl": "timestamp,original",
        "collapse": "digest",
        "limit": "1",
        "from": "2000",
    }
    try:
        response = await client.get(endpoint, params=params)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError, json.JSONDecodeError):
        return []

    if not isinstance(data, list) or len(data) < 2 or not data[1]:
        return []
    ts = str(data[1][0])
    if not re.fullmatch(r"\d{14}", ts):
        return []
    raw = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"
    return [_signal(
        kind="wayback_first_snapshot",
        raw=raw,
        source_url=str(response.url),
        confidence="diagnostic",
        usable=False,
        note="Earliest indexed snapshot proves observed existence by this date, not publication date.",
    )]


async def collect_date_diagnostic(target_url: str) -> dict:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; LeadGap-DateDiagnostic/1.0; +https://github.com/metatron9911-star/LeadGap-AI)"
    }
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(headers=headers, timeout=timeout, follow_redirects=True) as client:
        html, response_headers = await _fetch_text(client, target_url)
        if html is None:
            return {
                "target_url": target_url,
                "status": "fetch_failed",
                "signals": [],
                "defensible_publication_date": None,
            }

        signals = extract_html_date_signals(html, target_url)

        if response_headers and response_headers.get("Last-Modified"):
            signals.append(_signal(
                kind="http_last_modified",
                raw=response_headers["Last-Modified"],
                source_url=target_url,
                confidence="diagnostic",
                usable=False,
                note="HTTP Last-Modified is not publication proof.",
            ))

        signals.extend(await sitemap_signals(client, target_url))
        signals.extend(await feed_signals(client, target_url, html))
        signals.extend(await wayback_signal(client, target_url))

    strong = [
        s for s in signals
        if s.usable_as_publication_date and s.normalized_date
    ]
    # Prefer explicit page metadata over feed metadata; never use diagnostic-only timestamps.
    kind_rank = {
        "meta_article_published_time": 0,
        "meta_date_published": 1,
        "jsonld_datePublished": 2,
        "feed_pubDate": 3,
        "feed_published": 4,
    }
    strong.sort(key=lambda s: (kind_rank.get(s.kind, 99), s.normalized_date or "9999-99-99"))
    selected = strong[0] if strong else None

    return {
        "target_url": target_url,
        "status": "complete",
        "signals": [asdict(s) for s in signals],
        "defensible_publication_date": asdict(selected) if selected else None,
        "policy": {
            "publication_eligible": sorted(STRONG_PUBLICATION_KINDS),
            "diagnostic_only": sorted(DIAGNOSTIC_ONLY_KINDS),
            "rule": "Sitemap lastmod, HTTP Last-Modified, Wayback snapshots, and media filenames are never promoted to publication dates by this collector.",
        },
    }
