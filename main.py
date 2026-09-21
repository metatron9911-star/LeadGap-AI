import asyncio
import json
import os
import re
from difflib import SequenceMatcher
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from apify import Actor
from apify_client import ApifyClientAsync


GOOGLE_MAPS_ACTOR = "compass/crawler-google-places"


SUPPORTED = {
    "US": ("United States", "en"),
    "UK": ("United Kingdom", "en"),
    "CA": ("Canada", "en"),
    "AU": ("Australia", "en"),
    "NZ": ("New Zealand", "en"),
    "DE": ("Germany", "de"),
    "FR": ("France", "fr"),
    "BR": ("Brazil", "pt-BR"),
    "ES": ("Spain", "es"),
    "IT": ("Italy", "it"),
    "NL": ("Netherlands", "nl"),
    "IE": ("Ireland", "en"),
    "AE": ("United Arab Emirates", "en"),
    "SG": ("Singapore", "en"),
    "PL": ("Poland", "pl"),
}

ACCEPT_LANGUAGE = {
    "US": "en-US,en;q=0.9",
    "UK": "en-GB,en;q=0.9",
    "IE": "en-IE,en;q=0.9",
    "AU": "en-AU,en;q=0.9",
    "NZ": "en-NZ,en;q=0.9",
    "CA": "en-CA,en;q=0.9",
    "DE": "de-DE,de;q=0.9,en;q=0.8",
    "FR": "fr-FR,fr;q=0.9,en;q=0.8",
    "ES": "es-ES,es;q=0.9,en;q=0.8",
    "IT": "it-IT,it;q=0.9,en;q=0.8",
    "NL": "nl-NL,nl;q=0.9,en;q=0.8",
    "PL": "pl-PL,pl;q=0.9,en;q=0.8",
    "BR": "pt-BR,pt;q=0.9,en;q=0.8",
    "AE": "en-AE,en;q=0.9,ar;q=0.5",
    "SG": "en-SG,en;q=0.9",
}


PATTERNS = {
    "booking": (
        # English
        r"(book\s*(now|online|appointment)|"
        r"book\s+a\s+consultation|"
        r"schedule\s*(an\s*)?appointment|"
        r"make\s+an\s+appointment|"
        r"request\s+an\s+appointment|"
        r"online\s+booking|"
        # German
        r"termin\s*buchen|"
        r"online\s*termin|"
        r"termin\s*vereinbaren|"
        # French
        r"rendez[- ]?vous|"
        r"prendre\s+rendez|"
        # Spanish
        r"agendar|"
        r"marcar\s+consulta|"
        r"pedir\s+cita|"
        r"reservar\s+cita|"
        # Italian
        r"prenota(re|zione|zioni)?|"
        r"fissare\s+un\s+appuntamento|"
        # Dutch
        r"afspraak\s*maken|"
        r"maak\s+een\s+afspraak|"
        r"reserveren|"
        r"online\s+boeken|"
        # Polish
        r"rezerwacja|"
        r"zarezerwuj|"
        r"um[óo]w\s+(si[ęe]|wizyt[ęe])|"
        r"zapisz\s+si[ęe])"
    ),
    "contact_form": (
        r"(<form\b|"
        r"contact[-_ ]?form|"
        r"kontaktformular|"
        r"formulaire.{0,30}contact|"
        r"formul[aá]rio.{0,30}contato)"
    ),
    "live_chat": (
        r"(intercom|"
        r"crisp\.chat|"
        r"tawk\.to|"
        r"drift\.com|"
        r"livechatinc|"
        r"zendesk.{0,30}(chat|messenger)|"
        r"hubspot.{0,30}(chat|messages))"
    ),
    "ga4": (
        r"(googletagmanager\.com/gtag/js|"
        r"G-[A-Z0-9]{6,})"
    ),
    "gtm": (
        r"(googletagmanager\.com/gtm\.js|"
        r"GTM-[A-Z0-9]+)"
    ),
    "meta_pixel": (
        r"(connect\.facebook\.net/.+fbevents\.js|"
        r"fbq\s*\()"
    ),
    "cta": (
        r"(get\s+(a\s+)?quote|"
        r"request\s+(a\s+)?quote|"
        r"contact\s+us|"
        r"book\s+now|"
        r"book\s+online|"
        r"book\s+appointment|"
        r"schedule|"
        r"call\s+(us|now)|"
        r"make\s+an\s+appointment|"
        r"request\s+an\s+appointment|"
        r"termin|"
        r"kontakt|"
        r"rendez[- ]?vous|"
        r"contactez|"
        r"agendar|"
        r"or[cç]amento|"
        r"fale\s+conosco)"
    ),
}


IMPORTANT_LINK_WORDS = (
    # English
    "contact", "book", "booking", "appointment", "consultation",
    "enquiry", "enquiries", "get-in-touch", "schedule",
    # German
    "kontakt", "termin", "buchen", "beratung",
    # French
    "rendez", "consultation",
    # Spanish
    "contacto", "cita", "reservar", "consulta",
    # Italian
    "contatti", "contatto", "prenota", "prenotazione", "consulenza",
    # Dutch
    "afspraak", "boeken", "consult",
    # Polish
    "rezerwacja", "zarezerwuj", "konsultacja",
)


def normalize_url(url: str) -> str:
    url = (url or "").strip()

    if not url:
        return ""

    if not re.match(r"^https?://", url, re.I):
        url = "https://" + url

    return url


def clean_host(url: str) -> str:
    return urlparse(url).netloc.lower().replace("www.", "")


def detect_cms(html: str) -> str | None:
    low = html.lower()

    checks = [
        ("WordPress", ("wp-content", "wp-includes")),
        ("Wix", ("wixstatic.com", "wix.com")),
        ("Squarespace", ("squarespace.com", "static1.squarespace.com")),
        ("Shopify", ("cdn.shopify.com", "shopify.theme")),
        ("Webflow", ("webflow.js", "webflow.com")),
    ]

    for name, needles in checks:
        if any(n in low for n in needles):
            return name

    return None


def extract_business_name(
    soup: BeautifulSoup,
    fallback: str,
) -> str:

    def valid_name(text: str) -> bool:
        text = text.strip()

        if not 2 <= len(text) <= 100:
            return False

        digits = sum(ch.isdigit() for ch in text)
        letters = sum(ch.isalpha() for ch in text)

        if letters < 2:
            return False

        if digits > letters:
            return False

        if re.fullmatch(r"[ds()+-./]+", text):
            return False

        return True

    h1 = soup.find("h1")

    if h1:
        text = h1.get_text(" ", strip=True)

        if valid_name(text):
            return text

    if soup.title:
        title = soup.title.get_text(" ", strip=True)

        if title:
            title = re.split(
                r"s+[|–—-]s+",
                title,
            )[0].strip()

            if valid_name(title):
                return title

    return fallback


def find_candidate_pages(
    base_url: str,
    html: str,
    max_pages: int = 3,
) -> list[str]:

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    base_host = clean_host(base_url)

    scored = []

    for tag in soup.find_all("a", href=True):
        href = tag.get("href", "").strip()

        if not href:
            continue

        absolute = urljoin(
            base_url,
            href,
        )

        parsed = urlparse(absolute)

        if parsed.scheme not in ("http", "https"):
            continue

        if clean_host(absolute) != base_host:
            continue

        text = tag.get_text(
            " ",
            strip=True,
        ).lower()

        path = parsed.path.lower()

        haystack = f"{text} {path}"

        page_score = 0

        for word in IMPORTANT_LINK_WORDS:
            if word in haystack:
                page_score += 10

        if page_score <= 0:
            continue

        clean_url = absolute.split("#")[0]

        scored.append(
            (
                page_score,
                clean_url,
            )
        )

    scored.sort(
        key=lambda x: x[0],
        reverse=True,
    )

    output = []
    seen = set()

    for _, page_url in scored:
        if page_url in seen:
            continue

        if page_url.rstrip("/") == base_url.rstrip("/"):
            continue

        seen.add(page_url)
        output.append(page_url)

        if len(output) >= max_pages:
            break

    return output


def extract_contacts(
    html: str,
) -> tuple[list[str], list[str]]:

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    emails = set()
    phones = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()

        if href.lower().startswith("mailto:"):
            email = (
                href[7:]
                .split("?")[0]
                .strip()
                .lower()
            )

            if email:
                emails.add(email)

        elif href.lower().startswith("tel:"):
            phone = href[4:].strip()

            if phone:
                phones.add(phone)

    for email in re.findall(
        r"[A-Z0-9._%+-]+@[A-Z0-9.-]+.[A-Z]{2,}",
        html,
        re.I,
    ):
        emails.add(email.lower())

    return (
        sorted(emails)[:10],
        sorted(phones)[:10],
    )


def extract_social_links(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    out = {"facebook": None, "instagram": None}
    for a in soup.find_all("a", href=True):
        href = (a.get("href") or "").strip()
        host = clean_host(href) if href.startswith(("http://", "https://")) else ""
        if not out["facebook"] and ("facebook.com" in host or "fb.com" in host):
            out["facebook"] = href
        if not out["instagram"] and "instagram.com" in host:
            out["instagram"] = href
    return out


def has_contact_form(html: str) -> bool:
    """Detect enquiry/contact forms without treating every <form> as a lead form."""
    soup = BeautifulSoup(html, "html.parser")
    contact_words = re.compile(
        r"contact|enquir|message|quote|appointment|booking|callback|consult|"
        # German
        r"kontakt|anfrage|nachricht|termin|beratung|"
        # French
        r"rendez|message|demande|devis|"
        # Spanish
        r"contacto|cita|mensaje|consulta|presupuesto|"
        # Italian
        r"contatt|richiesta|preventivo|messaggio|consulenza|prenota|"
        # Dutch
        r"afspraak|bericht|aanvraag|offerte|"
        # Polish
        r"rezerwac|zapytanie|wiadomo|konsultacja|oferta",
        re.I,
    )
    field_hint = re.compile(
        r"(email|e-mail|phone|telephone|tel|mobile|message|"
        r"enquir|comment|question|details|"
        # German
        r"telefon|nachricht|bericht|name|vorname|nachname|anliegen|"
        # French
        r"t[ée]l[ée]phone|courriel|message|nom|pr[ée]nom|demande|"
        # Spanish
        r"tel[ée]fono|correo|mensaje|nombre|apellido|consulta|"
        # Italian
        r"telefono|messaggio|posta|nome|cognome|richiesta|"
        # Dutch
        r"telefoon|bericht|naam|voornaam|achternaam|aanvraag|"
        # Polish
        r"telefon|wiadomo[śs][ćc]|imi[ęe]|nazwisko|nazwa|zapytanie)",
        re.I,
    )

    for form in soup.find_all("form"):
        action = (form.get("action") or "").strip()
        identity = " ".join(
            str(form.get(attr) or "") for attr in ("id", "class", "name")
        )
        form_text = form.get_text(" ", strip=True)

        field_parts: list[str] = []
        for field in form.find_all(["input", "textarea", "select"]):
            field_parts.append(
                " ".join(
                    str(field.get(attr) or "")
                    for attr in ("type", "name", "id", "placeholder", "aria-label")
                )
            )
            label = field.find_parent("label")
            if label:
                field_parts.append(label.get_text(" ", strip=True))

        for label in form.find_all("label"):
            field_parts.append(label.get_text(" ", strip=True))

        field_text = " ".join(field_parts)
        haystack = f"{action} {identity} {form_text}"

        has_message = bool(
            re.search(
                r"message|enquir|details|comment|question|nachricht|mensaje|"
                r"messaggio|bericht|wiadomo",
                field_text,
                re.I,
            )
        )
        has_contact_field = bool(field_hint.search(field_text))
        has_contact_context = bool(contact_words.search(haystack))

        if has_contact_context and (has_message or has_contact_field):
            return True

    embedded_form_hosts = (
        "typeform.com", "hubspot.com", "hsforms.com",
        "jotform.com", "forms.gle", "calendly.com",
        "acuityscheduling.com", "setmore.com", "squareup.com/appointments",
    )
    for iframe in soup.find_all("iframe", src=True):
        src = (iframe.get("src") or "").strip().lower()
        if any(host in src for host in embedded_form_hosts):
            return True

    return False


def analyse_signals(
    combined_html: str,
) -> dict:

    low = combined_html.lower()

    soup = BeautifulSoup(
        combined_html,
        "html.parser",
    )

    visible_text = soup.get_text(
        " ",
        strip=True,
    )

    title_present = bool(
        soup.title
        and soup.title.get_text(strip=True)
    )

    meta_description = bool(
        soup.find(
            "meta",
            attrs={
                "name": re.compile(
                    "^description$",
                    re.I,
                )
            },
        )
    )

    analytics = bool(
        re.search(
            PATTERNS["ga4"],
            combined_html,
            re.I,
        )
        or re.search(
            PATTERNS["gtm"],
            combined_html,
            re.I,
        )
    )

    return {
        "https": False,

        "contact_form": has_contact_form(combined_html),

        "click_to_call": (
            'href="tel:' in low
            or "href='tel:" in low
        ),

        "booking": bool(
            re.search(
                PATTERNS["booking"],
                visible_text,
                re.I,
            )
        ),

        "live_chat": bool(
            re.search(
                PATTERNS["live_chat"],
                combined_html,
                re.I,
            )
        ),

        "ga4": bool(
            re.search(
                PATTERNS["ga4"],
                combined_html,
                re.I,
            )
        ),

        "gtm": bool(
            re.search(
                PATTERNS["gtm"],
                combined_html,
                re.I,
            )
        ),

        "analytics": analytics,

        "meta_pixel": bool(
            re.search(
                PATTERNS["meta_pixel"],
                combined_html,
                re.I,
            )
        ),

        "cta": bool(
            re.search(
                PATTERNS["cta"],
                visible_text,
                re.I,
            )
        ),

        "mobile_viewport": bool(
            soup.find(
                "meta",
                attrs={
                    "name": re.compile(
                        "^viewport$",
                        re.I,
                    )
                },
            )
        ),

        "title": title_present,
        "meta_description": meta_description,
    }


def build_opportunity(
    signals: dict,
    pages_scanned: int,
) -> dict:

    opportunities = []

    def add(
        key: str,
        missing: bool,
        weight: int,
        gap: str,
        opportunity: str,
        service: str,
        revenue_impact: str,
    ):

        if missing:
            opportunities.append(
                {
                    "key": key,
                    "weight": weight,
                    "gap": gap,
                    "opportunity": opportunity,
                    "service": service,
                    "revenueImpact": revenue_impact,
                }
            )

    add(
        "https",
        not signals["https"],
        15,
        "HTTPS not confirmed",
        "Website trust and technical reliability",
        "Website security / technical repair",
        "HIGH",
    )

    add(
        "booking",
        not signals["booking"],
        20,
        (
            "No clear online booking path detected "
            f"across {pages_scanned} scanned page(s)"
        ),
        "Booking conversion",
        "Online booking funnel implementation",
        "HIGH",
    )

    add(
        "cta",
        not signals["cta"],
        15,
        (
            "No strong conversion CTA detected "
            f"across {pages_scanned} scanned page(s)"
        ),
        "Conversion CTA optimization",
        "Conversion-focused website optimization",
        "HIGH",
    )

    add(
        "contact_form",
        not signals["contact_form"],
        12,
        (
            "No contact form detected "
            f"across {pages_scanned} scanned page(s)"
        ),
        "Lead capture",
        "Lead capture form implementation",
        "HIGH",
    )

    add(
        "click_to_call",
       not signals["click_to_call"],
        8,
        "No click-to-call telephone link detected",
        "Mobile lead capture",
        "Mobile contact conversion optimization",
        "MEDIUM",
    )

    add(
        "mobile_viewport",
        not signals["mobile_viewport"],
        8,
        "Mobile viewport configuration not detected",
        "Mobile conversion experience",
        "Mobile website optimization",
        "MEDIUM",
    )

    add(
        "analytics",
        not signals["analytics"],
        8,
        "No GA4 or Google Tag Manager detected",
        "Conversion measurement",
        "Analytics and conversion tracking setup",
        "MEDIUM",
    )

    add(
        "meta_pixel",
        not signals["meta_pixel"],
        4,
        "No Meta Pixel detected",
        "Paid social measurement",
        "Meta Ads tracking setup",
        "LOW",
    )

    add(
        "live_chat",
        not signals["live_chat"],
        4,
        "No live-chat technology detected",
        "After-hours enquiry capture",
        "Conversational lead capture",
        "LOW",
    )

    add(
        "meta_description",
        not signals["meta_description"],
        4,
        "Meta description not detected",
        "Search-result conversion",
        "SEO metadata optimization",
        "LOW",
    )

    opportunities.sort(
        key=lambda item: item["weight"],
        reverse=True,
    )

    score_value = min(
        sum(
            item["weight"]
            for item in opportunities
        ),
        100,
    )

    if score_value >= 60:
        level = "HIGH"

    elif score_value >= 35:
        level = "MEDIUM"

    else:
        level = "LOW"

    if opportunities:
        primary = opportunities[0]

    else:
        primary = {
            "opportunity": "General conversion optimization",
            "service": "Website conversion audit",
            "revenueImpact": "LOW",
            "gap": "No major conversion gap detected",
        }

    return {
        "score": score_value,
        "level": level,
        "primary": primary,
        "gaps": [
            item["gap"]
            for item in opportunities
        ],
        "opportunities": opportunities,
    }


def build_evidence(
    signals: dict,
    pages_scanned: int,
) -> list[str]:

    evidence = [
        (
            "Automated audit successfully scanned "
            f"{pages_scanned} public page(s)."
        )
    ]

    if signals["booking"]:
        evidence.append(
            "Online booking or appointment language detected."
        )
    else:
        evidence.append(
            "No clear booking or appointment path was detected."
        )

    if signals["contact_form"]:
        evidence.append(
            "Contact form detected."
        )
    else:
        evidence.append(
            "No contact form detected."
        )

    if signals["click_to_call"]:
        evidence.append(
            "Clickable telephone link detected."
        )
    else:
        evidence.append(
            "No clickable telephone link detected."
        )

    if signals["cta"]:
        evidence.append(
            "Strong conversion CTA language detected."
        )
    else:
        evidence.append(
            "Strong conversion CTA language was not detected."
        )

    if signals["analytics"]:
        evidence.append(
            "Google analytics/tag-management technology detected."
        )
    else:
        evidence.append(
            "GA4 or Google Tag Manager was not detected."
        )

    if signals["meta_pixel"]:
        evidence.append(
            "Meta Pixel detected."
        )
    else:
        evidence.append(
            "Meta Pixel was not detected."
        )

    if signals["mobile_viewport"]:
        evidence.append(
            "Mobile viewport configuration detected."
        )
    else:
        evidence.append(
            "Mobile viewport configuration was not detected."
        )

    return evidence


def 