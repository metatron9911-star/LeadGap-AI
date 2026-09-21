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


def _website_identity_key(url: str) -> str:
    """Deduplicate exact business pages, not every location on a shared domain."""
    normalized = normalize_url(url)
    if not normalized:
        return ""

    parsed = urlparse(normalized)
    host = (parsed.netloc or "").lower().replace("www.", "")
    path = re.sub(r"/+", "/", parsed.path or "/").rstrip("/")

    # Root/homepage URLs still dedupe at host level. Location/profile pages on
    # shared corporate domains remain distinct by path.
    return host if not path else f"{host}{path}"


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

        if re.fullmatch(r"[\d\s()+\-./]+", text):
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
                r"\s+[|–—-]\s+",
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
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
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
        r"\b(email|e-mail|phone|telephone|tel|mobile|message|"
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
        r"telefon|wiadomo[śs][ćc]|imi[ęe]|nazwisko|nazwa|zapytanie)\b",
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


def confidence_for_pages(
    pages_scanned: int,
    signals: dict | None = None,
    successful_fetches: int | None = None,
    attempted_fetches: int | None = None,
    contacts_found: bool = False,
) -> tuple[str, int]:
    """Confidence reflects audit quality, not merely page count."""
    signals = signals or {}
    successful_fetches = successful_fetches if successful_fetches is not None else pages_scanned
    attempted_fetches = attempted_fetches if attempted_fetches is not None else max(pages_scanned, 1)
    score = 45 + min(pages_scanned, 3) * 10
    if signals.get("title"):
        score += 5
    if signals.get("meta_description"):
        score += 5
    if signals.get("mobile_viewport"):
        score += 5
    if contacts_found:
        score += 5
    if attempted_fetches > 0:
        fetch_ratio = successful_fetches / attempted_fetches
        if fetch_ratio >= 1.0:
            score += 10
        elif fetch_ratio >= 0.66:
            score += 5
        elif fetch_ratio < 0.5:
            score -= 10
    score = max(20, min(score, 95))
    if score >= 85:
        return "HIGH", score
    if score >= 65:
        return "MEDIUM", score
    return "LOW", score


def qualify_sales_opportunity(
    opportunity: dict,
    signals: dict,
    confidence_score: int,
) -> dict:

    primary = opportunity["primary"]["opportunity"]

    score_value = opportunity["score"]

    sales_priority = "LOW"

    deal_type = "General website optimization"

    qualification_reason = (
        "The audit found technical gaps, "
        "but no strong standalone commercial "
        "opportunity was identified."
    )

    do_not_pitch = True


    if primary == "Booking conversion":

        sales_priority = "HIGH"
        deal_type = "Booking funnel"

        qualification_reason = (
            "The business has an active website, "
            "but no clear online booking path was detected. "
            "For an appointment-based business this creates "
            "a concrete conversion opportunity."
        )

        do_not_pitch = False


    elif primary == "Lead capture":

        sales_priority = "HIGH"
        deal_type = "Lead capture"

        qualification_reason = (
            "The website is active, but no contact form "
            "was detected. High-intent visitors may face "
            "unnecessary friction when trying to enquire."
        )

        do_not_pitch = False


    elif primary == "Conversion CTA optimization":

        sales_priority = "HIGH"
        deal_type = "Conversion optimization"

        qualification_reason = (
            "The website lacks a clearly detected conversion CTA. "
            "This creates a commercially actionable opportunity "
            "to improve visitor-to-enquiry flow."
        )

        do_not_pitch = False


    elif primary == "Mobile conversion experience":

        sales_priority = "MEDIUM"
        deal_type = "Mobile conversion"

        qualification_reason = (
            "The audit found a potential mobile conversion issue "
            "that warrants targeted review."
        )

        do_not_pitch = confidence_score < 75


    elif primary == "Mobile lead capture":

        sales_priority = "MEDIUM"
        deal_type = "Mobile lead capture"

        qualification_reason = (
            "No click-to-call link was detected. "
            "For a local service business this may add friction "
            "for high-intent mobile visitors."
        )

        do_not_pitch = confidence_score < 75


    elif primary == "Conversion measurement":

        deal_type = "Tracking setup"

        if (
            not signals.get("analytics")
            and not signals.get("meta_pixel")
            and score_value >= 15
        ):

            sales_priority = "MEDIUM"

            qualification_reason = (
                "Multiple marketing measurement signals "
                "were not detected. This may make advertising "
                "and website conversions harder to measure."
            )

            do_not_pitch = True

        else:

            sales_priority = "LOW"

            qualification_reason = (
                "A tracking-related gap was detected, "
                "but it is not strong enough by itself "
                "to justify priority outreach."
            )

            do_not_pitch = True


    elif primary == "Paid social measurement":

        sales_priority = "LOW"
        deal_type = "Meta Ads tracking"

        qualification_reason = (
            "Meta Pixel was not detected, but this alone "
            "does not prove that the business needs "
            "paid-social tracking or runs Meta advertising."
        )

        do_not_pitch = True


    elif primary == "After-hours enquiry capture":

        sales_priority = "LOW"
        deal_type = "Live chat"

        qualification_reason = (
            "No live chat was detected, but absence of chat "
            "alone is not a strong enough commercial reason "
            "for outreach."
        )

        do_not_pitch = True


    elif primary == "Search-result conversion":

        sales_priority = "LOW"
        deal_type = "SEO metadata"

        qualification_reason = (
            "A metadata gap was detected, "
            "but this is a relatively small "
            "standalone opportunity."
        )

        do_not_pitch = True


    elif primary == "Website trust and technical reliability":

        sales_priority = "HIGH"
        deal_type = "Website technical repair"

        qualification_reason = (
            "HTTPS was not confirmed. "
            "If verified manually, this is a significant "
            "trust and technical issue worth addressing."
        )

        do_not_pitch = confidence_score < 75


    # Confidence → Sales Priority
    # HIGH allowed only at 90+

    if confidence_score < 60:

        do_not_pitch = True
        sales_priority = "LOW"

        qualification_reason += (
            " Automated confidence is below the minimum "
            "required for commercial outreach. "
            "Manual verification is required."
        )

    elif confidence_score < 90:

        if sales_priority == "HIGH":

            sales_priority = "MEDIUM"

            qualification_reason += (
                f" Confidence score is {confidence_score}, "
                "so Sales Priority was capped at MEDIUM. "
                "Manual verification is recommended before outreach."
            )


    return {
        "salesPriority": sales_priority,
        "estimatedDealType": deal_type,
        "qualificationReason": qualification_reason,
        "doNotPitch": do_not_pitch,
    }


def make_pitch(
    business_name: str,
    domain: str,
    opportunity: dict,
    pages_scanned: int,
) -> tuple[str, str]:

    primary = opportunity["primary"]["opportunity"]

    why = (
        f"{business_name} has an active public website, "
        f"but the automated audit found a specific "
        f"{primary.lower()} opportunity after checking "
        f"{pages_scanned} page(s). "
        "This gives an agency a concrete reason "
        "to approach the business instead of sending "
        "a generic website pitch."
    )

    gap = opportunity["primary"]["gap"]

    pitch = (
        f"I reviewed {domain} and noticed a potential "
        f"conversion gap: {gap}. "
        "There may be an opportunity to improve the path "
        "from website visitor to enquiry or booked appointment. "
        "I can show you the exact change I would test first."
    )

    return why, pitch


async def fetch_page(
    client: httpx.AsyncClient,
    url: str,
    retries: int = 2,
) -> tuple[str, int, str]:
    last_exc: Exception | None = None
    for attempt in range(retries + 1):
        try:
            response = await client.get(url, follow_redirects=True)
            if response.status_code >= 500 and attempt < retries:
                await asyncio.sleep(0.6 * (2 ** attempt))
                continue
            return str(response.url), response.status_code, response.text[:5_000_000]
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_exc = exc
            if attempt >= retries:
                raise
            await asyncio.sleep(0.6 * (2 ** attempt))
    if last_exc:
        raise last_exc
    raise RuntimeError("Website fetch failed without a response")


DISCOVERY_BLOCKED_DOMAINS = (
    "google.com",
    "google.co.uk",
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "x.com",
    "twitter.com",
    "youtube.com",
    "yelp.com",
    "yell.com",
    "tripadvisor.com",
    "nhs.uk",
    "192.com",
    "cylex-uk.co.uk",
    "find-open.co.uk",
    "opendi.co.uk",
    "bizseek.co.uk",
    "mapquest.com",
    "dental-art.co.uk",
    "dentist-london.com",
)


def _search_result_target(href: str) -> str:
    """Extract a real target URL from a DuckDuckGo result link."""
    if not href:
        return ""

    href = href.strip()

    if href.startswith("//"):
        href = "https:" + href

    try:
        parsed = urlparse(href)

        if "duckduckgo.com" in (parsed.hostname or ""):
            params = parse_qs(parsed.query)
            uddg = params.get("uddg", [""])[0]
            if uddg:
                return unquote(uddg)
    except Exception:
        return ""

    if href.startswith("http://") or href.startswith("https://"):
        return href

    return ""


def _blocked_discovery_domain(url: str) -> bool:
    host = clean_host(url)

    if not host:
        return True

    return any(
        host == blocked or host.endswith("." + blocked)
        for blocked in DISCOVERY_BLOCKED_DOMAINS
    )


def _business_tokens(name: str) -> set[str]:
    stop = {
        "the", "and", "of", "at", "in", "a", "an",
        "ltd", "limited", "llc", "inc", "plc", "company",
        "practice", "clinic", "surgery", "centre", "center",
        "dental", "dentist", "dentistry",
        "plumber", "plumbing", "roofer", "roofing", "cleaner", "cleaning",
        "law", "legal", "lawyer", "attorney", "solicitor",
        "accountant", "accounting", "spa", "salon", "beauty",
    }

    tokens = {
        token
        for token in re.findall(r"[a-z0-9]+", (name or "").lower())
        if len(token) >= 3 and token not in stop
    }

    return tokens


def _external_candidate_score(
    url: str,
    title: str,
    snippet: str,
    business_name: str,
    city: str,
    address: str,
) -> int:
    """Relevance score with an identity-evidence guard for official-site matching."""
    if not url or _blocked_discovery_domain(url):
        return -100
    haystack = " ".join([clean_host(url), title or "", snippet or ""]).lower()
    name_tokens = _business_tokens(business_name)
    matched_name_tokens = sum(1 for token in name_tokens if token in haystack)
    score = 4 if matched_name_tokens >= 2 else 2 if matched_name_tokens == 1 else 0
    city_clean = (city or "").strip().lower()
    city_match = bool(city_clean and city_clean in haystack)
    if city_match:
        score += 1
    postcode_match_found = False
    postcode_match = re.search(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", address or "", flags=re.I)
    if postcode_match:
        postcode = re.sub(r"\s+", "", postcode_match.group(0)).lower()
        haystack_compact = re.sub(r"\s+", "", haystack)
        if postcode in haystack_compact:
            postcode_match_found = True
            score += 2
    host = clean_host(url)
    host_name_match = any(token in host for token in name_tokens)
    if host_name_match:
        score += 2
    # A directory/profile page can contain the exact business name and city.
    # Require a stronger identity anchor before treating a result as official:
    # either a distinctive business-name token in the host or the Maps postcode.
    if not (postcode_match_found or host_name_match):
        return min(score, 3)
    return score


async def find_external_business_website(
    client: httpx.AsyncClient,
    place: dict,
    city: str,
) -> dict:
    """
    Try to find an official website when Google Maps has no website link.

    This is intentionally conservative: a candidate is accepted only when
    search-result evidence strongly matches the business name/location.
    """
    business_name = (place.get("title") or "").strip()
    address = (place.get("address") or "").strip()

    if not business_name:
        return {
            "status": "SKIPPED",
            "website": "",
            "evidence": "Business name was unavailable for external website verification.",
        }

    query_parts = [f'"{business_name}"']
    if city:
        query_parts.append(city)
    query_parts.append("official website")

    query = " ".join(query_parts)

    # Be deliberately polite to DuckDuckGo's HTML endpoint. Discovery runs
    # sequentially, so this creates a minimum delay between external checks and
    # reduces 429/403 bursts when many Maps listings have no website attached.
    await asyncio.sleep(0.6)

    try:
        response = await client.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            follow_redirects=True,
        )

        if response.status_code >= 400 or response.status_code == 202:
            return {
                "status": "UNAVAILABLE",
                "website": "",
                "evidence": f"External website search returned HTTP {response.status_code}.",
            }

        soup = BeautifulSoup(response.text, "html.parser")
        result_nodes = soup.select(".result")
        if not result_nodes:
            return {
                "status": "UNAVAILABLE",
                "website": "",
                "evidence": (
                    "External search returned no parsable results; "
                    "verification inconclusive."
                ),
            }

        candidates: list[tuple[int, str, str]] = []

        for result in result_nodes[:10]:
            link = result.select_one(".result__a")
            if not link:
                continue

            target = _search_result_target(link.get("href", ""))
            if not target:
                continue

            title = link.get_text(" ", strip=True)
            snippet_node = result.select_one(".result__snippet")
            snippet = (
                snippet_node.get_text(" ", strip=True)
                if snippet_node
                else ""
            )

            score = _external_candidate_score(
                url=target,
                title=title,
                snippet=snippet,
                business_name=business_name,
                city=city,
                address=address,
            )

            candidates.append((score, target, title))

        candidates.sort(key=lambda row: row[0], reverse=True)

        if candidates and candidates[0][0] >= 4:
            best_score, best_url, best_title = candidates[0]
            return {
                "status": "FOUND",
                "website": normalize_url(best_url),
                "evidence": (
                    f"A likely official website was found outside Google Maps "
                    f"(match score {best_score}): {best_title}"
                ),
            }

        return {
            "status": "NOT_FOUND",
            "website": "",
            "evidence": (
                "No sufficiently strong official-website match was found in the "
                "external search results. This does not prove that no website exists."
            ),
        }

    except Exception as exc:
        Actor.log.warning(
            "External website verification failed for %s: %s",
            business_name,
            exc,
        )

        return {
            "status": "UNAVAILABLE",
            "website": "",
            "evidence": "External website verification could not be completed.",
        }

def make_no_website_lead(
    place: dict,
    country: str,
    city: str,
    business_type: str,
    verification: dict | None = None,
) -> dict:

    business_name = (
        place.get("title")
        or "Unknown business"
    )

    phone = place.get("phone")
    verification = verification or {}
    verification_status = verification.get("status", "NOT_RUN")
    verification_evidence = verification.get(
        "evidence",
        "External website verification was not run.",
    )

    # We never claim that the business definitely has no website.
    # Search completed with no strong match -> stronger lead.
    # Search unavailable -> still useful, but manual verification is more important.
    if verification_status == "NOT_FOUND":
        confidence = "MEDIUM"
        confidence_score = 85
        sales_priority = "HIGH"
        opportunity_score = 90
    else:
        confidence = "LOW"
        confidence_score = 50
        sales_priority = "LOW"
        opportunity_score = 60

    return {
        "business": business_name,
        "businessName": business_name,
        "website": "",

        "country": country,
        "city": city,
        "businessType": business_type,

        "mapAddress": place.get("address"),
        "mapPhone": phone,
        "mapCategory": _place_primary_category(place),
        "mapRating": place.get("totalScore"),
        "mapReviewsCount": place.get("reviewsCount"),
        "mapPlaceId": place.get("placeId"),

        "externalWebsiteCheck": verification_status,
        "externalWebsiteEvidence": verification_evidence,
        "websiteSource": "NOT_FOUND",

        "reachable": False,
        "auditStatus": "NO_WEBSITE_LINKED",

        "opportunityScore": opportunity_score,
        "opportunityLevel": "HIGH" if sales_priority == "HIGH" else "MEDIUM",

        "confidence": confidence,
        "confidenceScore": confidence_score,

        "primaryOpportunity": "Website presence",
        "revenueImpact": "HIGH",

        "salesPriority": sales_priority,
        "estimatedDealType": "Website creation / Google Maps website setup",

        "qualificationReason": (
            "No website is linked to this business in Google Maps. "
            + (
                "An additional external search did not find a sufficiently strong "
                "official-website match. This is a strong website-presence lead, "
                "but absence of a website is still not proven and should be checked before outreach."
                if verification_status == "NOT_FOUND"
                else
                "The additional external website check could not confirm whether an "
                "independent website exists, so manual verification is required before outreach."
            )
        ),

        "doNotPitch": verification_status != "NOT_FOUND",

        "emails": [],

        "phones": (
            [phone]
            if phone
            else []
        ),

        "gaps": [
            "No website linked in Google Maps"
        ],

        "evidence": [
            "Business discovered through Google Maps.",
            "No website URL is linked to the Google Maps listing.",
            verification_evidence,
        ],

        "recommendedService": (
            "Website creation or Google Maps website-link optimization"
        ),

        "whyThisLead": (
            f"{business_name} has no website linked in Google Maps. "
            + (
                "A separate external search also found no sufficiently strong official-site match. "
                "This makes it a strong digital-presence opportunity, subject to final manual verification."
                if verification_status == "NOT_FOUND"
                else
                "External verification was inconclusive, so this remains a useful but lower-confidence "
                "digital-presence lead until manually checked."
            )
        ),

        "pitchHook": (
            f"I found {business_name} while reviewing local "
            f"{business_type} businesses in {city}. "
            "I noticed there is currently no website linked to the Google Maps listing. "
            "If the business does not already have an active website, there may be "
            "an opportunity to create a conversion-focused site and connect it directly to local search."
        ),
    }


async def audit(
    client: httpx.AsyncClient,
    raw_url: str,
    country: str,
) -> dict:

    url = normalize_url(raw_url)

    domain = (
        clean_host(url)
        if url
        else raw_url
    )

    base_result = {
        "business": domain,
        "businessName": domain,
        "website": url,
        "websiteSource": "DIRECT_INPUT",
        "country": country,
        "language": SUPPORTED[country][1],
        "reachable": False,
        "auditStatus": "NOT_STARTED",
    }

    try:

        (
            final_url,
            status,
            homepage_html,
        ) = await fetch_page(
            client,
            url,
        )


        if status >= 400:

            base_result.update(
                {
                    "website": final_url,
                    "httpStatus": status,
                    "auditStatus": f"HTTP_{status}",

                    "opportunityScore": 0,
                    "opportunityLevel": "LOW",

                    "confidence": "LOW",
                    "confidenceScore": 20,

                    "salesPriority": "LOW",
                    "estimatedDealType": "Manual review",

                    "qualificationReason": (
                        "The automated request failed, "
                        "which is not enough evidence for outreach."
                    ),

                    "doNotPitch": True,

                    "gaps": [],

                    "evidence": [
                        (
                            f"The website returned HTTP {status}. "
                            "A failed automated request is not treated "
                            "as proof of a sales opportunity."
                        )
                    ],

                    "recommendedService": (
                        "Manual review required"
                    ),

                    "primaryOpportunity": (
                        "Manual verification"
                    ),

                    "revenueImpact": "UNKNOWN",

                    "whyThisLead": (
                        "The automated audit could not reliably "
                        "inspect the website."
                    ),

                    "pitchHook": (
                        "Manual website review required "
                        "before outreach."
                    ),
                }
            )

            return base_result


        homepage_soup = BeautifulSoup(
            homepage_html,
            "html.parser",
        )

        business_name = extract_business_name(
            homepage_soup,
            clean_host(final_url),
        )


        candidate_pages = find_candidate_pages(
            final_url,
            homepage_html,
            max_pages=3,
        )


        scanned = [
            {
                "url": final_url,
                "status": status,
                "html": homepage_html,
            }
        ]


        for page_url in candidate_pages:

            try:

                (
                    page_final_url,
                    page_status,
                    page_html,
                ) = await fetch_page(
                    client,
                    page_url,
                )

                if page_status < 400:

                    scanned.append(
                        {
                            "url": page_final_url,
                            "status": page_status,
                            "html": page_html,
                        }
                    )

            except Exception:
                continue


        combined_html = "\n".join(
            page["html"]
            for page in scanned
        )


        signals = analyse_signals(
            combined_html
        )

        signals["https"] = (
            final_url
            .lower()
            .startswith("https://")
        )


        opportunity = build_opportunity(
            signals,
            len(scanned),
        )


        evidence = build_evidence(
            signals,
            len(scanned),
        )


        emails, phones = extract_contacts(
            combined_html
        )
        social_links = extract_social_links(combined_html)


        (
            confidence,
            confidence_score,
        ) = confidence_for_pages(
            len(scanned),
            signals=signals,
            successful_fetches=len(scanned),
            attempted_fetches=1 + len(candidate_pages),
            contacts_found=bool(emails or phones),
        )


        (
            why_this_lead,
            pitch_hook,
        ) = make_pitch(
            business_name,
            clean_host(final_url),
            opportunity,
            len(scanned),
        )


        sales = qualify_sales_opportunity(
            opportunity,
            signals,
            confidence_score,
        )


        return {
            "business": clean_host(final_url),
            "businessName": business_name,
            "website": final_url,

            "country": country,
            "language": SUPPORTED[country][1],

            "reachable": True,
            "auditStatus": "SUCCESS",
            "httpStatus": status,

            "cms": detect_cms(
                combined_html
            ),

            "pagesScanned": len(scanned),

            "pagesChecked": [
                page["url"]
                for page in scanned
            ],

            "emails": emails,
            "phones": phones,
            "facebook": social_links.get("facebook"),
            "instagram": social_links.get("instagram"),

            "signals": signals,

            "opportunityScore": (
                opportunity["score"]
            ),

            "opportunityLevel": (
                opportunity["level"]
            ),

            "confidence": confidence,
            "confidenceScore": confidence_score,

            "primaryOpportunity": (
                opportunity["primary"]["opportunity"]
            ),

            "revenueImpact": (
                opportunity["primary"]["revenueImpact"]
            ),

            "salesPriority": (
                sales["salesPriority"]
            ),

            "estimatedDealType": (
                sales["estimatedDealType"]
            ),

            "qualificationReason": (
                sales["qualificationReason"]
            ),

            "doNotPitch": (
                sales["doNotPitch"]
            ),

            "gaps": opportunity["gaps"],

            "evidence": evidence,

            "recommendedService": (
                opportunity["primary"]["service"]
            ),

            "whyThisLead": why_this_lead,

            "pitchHook": pitch_hook,

            "opportunities": (
                opportunity["opportunities"]
            ),
        }


    except Exception as exc:

        base_result.update(
            {
                "auditStatus": "FETCH_FAILED",

                "opportunityScore": 0,
                "opportunityLevel": "LOW",

                "confidence": "LOW",
                "confidenceScore": 10,

                "salesPriority": "LOW",
                "estimatedDealType": "Manual review",

                "qualificationReason": (
                    "The automated audit failed, "
                    "so there is not enough evidence "
                    "for outreach."
                ),

                "doNotPitch": True,

                "gaps": [],

                "evidence": [
                    (
                        "The automated audit failed "
                        "to retrieve the website. "
                        "This is not treated as evidence "
                        "of a sales opportunity."
                    )
                ],

                "recommendedService": (
                    "Manual review required"
                ),

                "primaryOpportunity": (
                    "Manual verification"
                ),

                "revenueImpact": "UNKNOWN",

                "whyThisLead": (
                    "The website must be manually "
                    "checked before outreach."
                ),

                "pitchHook": (
                    "Manual review required before "
                    "contacting this business."
                ),

                "error": str(exc)[:300],
            }
        )

        return base_result


def _normalize_dedupe_text(value: str) -> str:
    """Normalize business names/addresses for conservative duplicate detection."""
    text = (value or "").lower().strip()
    text = text.replace("united kingdom", "uk")
    text = text.replace("great britain", "uk")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _normalize_phone(value: str) -> str:
    """Keep digits only so differently formatted versions of the same phone match."""
    digits = re.sub(r"\D+", "", value or "")
    # Comparing the last 10 digits is useful when one source uses +44 and another 0.
    return digits[-10:] if len(digits) >= 10 else digits


def _names_are_similar(a: str, b: str) -> bool:
    a_norm = _normalize_dedupe_text(a)
    b_norm = _normalize_dedupe_text(b)

    if not a_norm or not b_norm:
        return False

    if a_norm == b_norm:
        return True

    return SequenceMatcher(None, a_norm, b_norm).ratio() >= 0.78


def _same_address(a: str, b: str) -> bool:
    a_norm = _normalize_dedupe_text(a)
    b_norm = _normalize_dedupe_text(b)

    if not a_norm or not b_norm:
        return False

    if a_norm == b_norm:
        return True

    # Handles small country/postcode formatting differences while remaining conservative.
    return (
        len(a_norm) >= 15
        and len(b_norm) >= 15
        and (a_norm in b_norm or b_norm in a_norm)
    )


def _place_quality(place: dict) -> tuple:
    """Prefer the richer Maps record when two records represent the same business."""
    return (
        1 if place.get("website") else 0,
        1 if place.get("phone") else 0,
        1 if place.get("totalScore") is not None else 0,
        int(place.get("reviewsCount") or 0),
    )


def _places_are_duplicates(a: dict, b: dict) -> bool:
    # Same Google place ID is definitive.
    a_place_id = (a.get("placeId") or "").strip()
    b_place_id = (b.get("placeId") or "").strip()
    if a_place_id and b_place_id and a_place_id == b_place_id:
        return True

    # Same phone can be a central franchise/call-center number.
    a_phone = _normalize_phone(a.get("phone") or "")
    b_phone = _normalize_phone(b.get("phone") or "")
    if a_phone and b_phone and a_phone == b_phone:
        a_address = a.get("address") or ""
        b_address = b.get("address") or ""
        if not (a_address and b_address and not _same_address(a_address, b_address)):
            return True

    # Same address alone is not enough: multiple businesses can share a building.
    # Require a similar business name as well.
    if _same_address(a.get("address") or "", b.get("address") or ""):
        return _names_are_similar(
            a.get("title") or "",
            b.get("title") or "",
        )

    return False


def deduplicate_places(places: list[dict]) -> list[dict]:
    """
    Remove duplicate Google Maps businesses using place ID, phone, and
    address + similar name. Keep the richest record among duplicates.
    """
    # Richer records are considered first, so the kept record is normally the
    # one with website/phone/rating/reviews rather than an incomplete duplicate.
    ordered = sorted(places, key=_place_quality, reverse=True)
    unique: list[dict] = []

    for place in ordered:
        duplicate = any(
            _places_are_duplicates(place, kept)
            for kept in unique
        )

        if duplicate:
            Actor.log.info(
                "Skipping duplicate Maps listing: %s | %s",
                place.get("title") or "Unknown business",
                place.get("address") or "No address",
            )
            continue

        unique.append(place)

    Actor.log.info(
        "Deduplication: %s Maps listings -> %s unique businesses.",
        len(places),
        len(unique),
    )

    return unique


async def discover_businesses(
    country: str,
    city: str,
    business_type: str,
    max_businesses: int,
) -> list[dict]:

    token = os.getenv("APIFY_TOKEN")

    if not token:
        raise RuntimeError(
            "APIFY_TOKEN is not available. "
            "Automatic discovery requires an Apify Platform run."
        )

    country_name = SUPPORTED[country][0]
    language = SUPPORTED[country][1]

    location_query = (
        f"{city}, {country_name}"
    )

    Actor.log.info(
        "Discovering up to %s '%s' businesses in %s",
        max_businesses,
        business_type,
        location_query,
    )


    apify_client = ApifyClientAsync(
        token
    )


    maps_input = {
        "searchStringsArray": [
            business_type
        ],

        "locationQuery": location_query,

        "maxCrawledPlacesPerSearch": (
            max_businesses
        ),

        "language": language,

        "scrapeContacts": False,

        "scrapeSocialMediaProfiles": {
            "facebooks": False,
            "instagrams": False,
            "youtubes": False,
            "tiktoks": False,
            "twitters": False,
        },

        "maximumLeadsEnrichmentRecords": 0,
    }


    actor_client = (
        apify_client.actor(
            GOOGLE_MAPS_ACTOR
        )
    )


    run = await actor_client.call(
        run_input=maps_input
    )


    if run is None:

        raise RuntimeError(
            "Google Maps discovery Actor failed."
        )


    # apify-client 1.x returns run metadata as a dict, while newer
    # clients may expose attributes. Support both without changing logic.
    default_dataset_id = (
        run.get("defaultDatasetId")
        if isinstance(run, dict)
        else getattr(run, "default_dataset_id", None)
    )

    if not default_dataset_id:
        raise RuntimeError(
            "Google Maps discovery Actor returned no default dataset ID."
        )

    dataset_client = (
        apify_client.dataset(
            default_dataset_id
        )
    )


    # list_items() is object-like in apify-client 1.x, but keep a dict
    # fallback for compatibility with alternate client return shapes.

    page = await dataset_client.list_items(
        limit=max_businesses
    )

    page_items = (
        page.get("items", [])
        if isinstance(page, dict)
        else getattr(page, "items", [])
    )

    places = list(
        page_items
    )


    Actor.log.info(
        "Google Maps discovery returned %s businesses.",
        len(places),
    )


    return places


def _norm_niche_text(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _place_primary_category(place: dict) -> str:
    """Return the primary Maps category across current scraper field shapes."""
    category = place.get("category") or place.get("categoryName")
    if category:
        return str(category)
    categories = place.get("categories") or []
    if isinstance(categories, str):
        return categories
    if categories:
        return str(categories[0])
    return ""


# Единый rule-объект для ниш с разным написанием (med spa / medspa)
_MED_SPA_RULE = {
    "title_positive": (
        "med spa", "medspa", "aesthetic", "botox", "filler",
        "laser", "skin clinic", "derma", "cosmetic",
    ),
    "category_positive": (
        "medical spa", "skin care clinic", "cosmetic surgeon",
        "dermatologist", "aesthetician",
    ),
    "title_conflicts": (
        "veterinary", "general practitioner", "hospital", "pharmacy",
    ),
}

# General wellness/day-spa queries are broader than medical aesthetics.
_SPA_RULE = {
    "title_positive": (
        "spa", "wellness", "massage", "sauna", "hammam", "wellbeing",
    ),
    "category_positive": (
        "day spa", "spa", "massage spa", "wellness center",
        "wellness centre", "massage therapist", "sauna",
    ),
    "title_conflicts": (
        "spa supplies", "pool supply", "hot tub store", "equipment",
    ),
}


NICHE_RULES = {
    # ------------------------------------------------------------------ #
    # Home services (существующие правила, немного уточнены)             #
    # ------------------------------------------------------------------ #
    "plumber": {
        "title_positive": (
            "plumb", "plumber", "heating", "boiler", "gas engineer",
            "drain", "bathroom", "pipework", "central heating",
        ),
        "category_positive": (
            "plumber", "plumbing service", "heating contractor",
            "gas engineer", "drainage service", "bathroom remodeler",
        ),
        "title_conflicts": (
            "construction", "builder", "builders", "building services",
            "property maintenance", "handyman", "kitchen fitter",
            "bathroom showroom",
        ),
    },
    "electrician": {
        "title_positive": ("electric", "electrical", "electrician"),
        "category_positive": (
            "electrician", "electrical installation", "electrical engineer",
        ),
        "title_conflicts": ("builder", "construction", "hardware"),
    },
    "roofer": {
        "title_positive": ("roof", "roofing", "roofer"),
        "category_positive": ("roofer", "roofing contractor", "roofing service"),
        "title_conflicts": ("builder", "construction", "hardware"),
    },
    "builder": {
        "title_positive": ("builder", "building", "construction"),
        "category_positive": (
            "builder", "construction company", "contractor",
        ),
        "title_conflicts": (),
    },
    "hvac": {
        "title_positive": (
            "hvac", "heating", "cooling", "air conditioning", "ventilation",
        ),
        "category_positive": (
            "hvac contractor", "air conditioning contractor",
            "heating contractor", "furnace repair",
        ),
        "title_conflicts": ("builder", "construction", "hardware"),
    },
    "locksmith": {
        "title_positive": ("lock", "locksmith", "key"),
        "category_positive": ("locksmith",),
        "title_conflicts": ("hardware", "security system", "car dealer"),
    },
    "cleaner": {
        "title_positive": ("clean", "cleaning", "maid", "janitorial"),
        "category_positive": (
            "cleaning service", "house cleaning", "commercial cleaning",
        ),
        "title_conflicts": ("laundry", "dry cleaning", "car wash"),
    },
    "landscaper": {
        "title_positive": ("landscape", "garden", "lawn", "tree"),
        "category_positive": ("landscaper", "gardener", "lawn care service"),
        "title_conflicts": ("nursery", "garden center"),
    },
    "pest control": {
        "title_positive": ("pest", "exterminator", "termite"),
        "category_positive": ("pest control service", "exterminator"),
        "title_conflicts": ("hardware",),
    },
    "handyman": {
        "title_positive": ("handyman", "maintenance", "odd job"),
        "category_positive": ("handyman", "handyman service"),
        "title_conflicts": ("builder", "construction"),
    },

    # ------------------------------------------------------------------ #
    # Health & dental — самые маржинальные B2B-лиды                     #
    # ------------------------------------------------------------------ #
    "dentist": {
        "title_positive": (
            "dental", "dentist", "orthodont", "endodont", "periodont",
            "oral surgery", "smile", "teeth",
        ),
        "category_positive": (
            "dentist", "dental clinic", "orthodontist", "oral surgeon",
            "pediatric dentist", "cosmetic dentist", "dental",
        ),
        "title_conflicts": (
            "veterinary", "animal", "pet hospital", "dermatolog",
        ),
    },
    "orthodontist": {
        "title_positive": ("orthodont", "braces", "aligner"),
        "category_positive": ("orthodontist", "dental", "dentist"),
        "title_conflicts": ("veterinary",),
    },
    "med spa": _MED_SPA_RULE,
    "medspa":   _MED_SPA_RULE,
    "aesthetics": _MED_SPA_RULE,

    # ------------------------------------------------------------------ #
    # Legal — высокий чек, много неэффективных сайтов                    #
    # ------------------------------------------------------------------ #
    "lawyer": {
        "title_positive": (
            "law", "legal", "solicitor", "attorney", "lawyer",
            "barrister", "advocate",
        ),
        "category_positive": (
            "lawyer", "law firm", "legal services", "attorney", "solicitor",
        ),
        "title_conflicts": ("insurance", "real estate", "accounting"),
    },
    "solicitor": {
        "title_positive": ("solicitor", "law", "legal"),
        "category_positive": ("lawyer", "law firm", "legal services"),
        "title_conflicts": ("insurance",),
    },

    # ------------------------------------------------------------------ #
    # Beauty & wellness — идеально под booking-gap питч                  #
    # ------------------------------------------------------------------ #
    "beauty salon": {
        "title_positive": (
            "salon", "beauty", "hair", "nail", "lash", "brow",
            "makeup", "aesthetic",
        ),
        "category_positive": (
            "beauty salon", "hair salon", "nail salon", "day spa",
            "beauty", "hairdresser",
        ),
        "title_conflicts": ("barber", "pharmacy", "cosmetics store"),
    },
    "hair salon": {
        "title_positive": ("hair", "salon", "barber", "stylist"),
        "category_positive": ("hair salon", "barber", "hairdresser"),
        "title_conflicts": ("beauty supply", "cosmetics store"),
    },
    "nail salon": {
        "title_positive": ("nail", "manicure", "pedicure"),
        "category_positive": ("nail salon", "beauty salon"),
        "title_conflicts": ("hardware",),
    },

    # ------------------------------------------------------------------ #
    # Food & hospitality                                                 #
    # ------------------------------------------------------------------ #
    "restaurant": {
        "title_positive": (
            "restaurant", "cafe", "bistro", "pizzeria", "trattoria",
            "diner", "kitchen", "eatery",
        ),
        "category_positive": (
            "restaurant", "cafe", "bistro", "pizza", "italian restaurant",
            "fast food", "diner",
        ),
        "title_conflicts": (
            "catering", "food truck", "grocery", "supermarket",
        ),
    },

    # ------------------------------------------------------------------ #
    # Professional services                                              #
    # ------------------------------------------------------------------ #
    "accountant": {
        "title_positive": (
            "account", "bookkeep", "tax", "audit", "cpa", "chartered",
        ),
        "category_positive": (
            "accountant", "bookkeeping service", "tax consultant",
            "certified public accountant", "accounting firm",
        ),
        "title_conflicts": ("bank", "insurance", "loan"),
    },
}

# Short user queries should resolve to the same relevance rules as their
# canonical niche names. Keep aliases after NICHE_RULES is fully defined.
NICHE_RULES["dental"] = NICHE_RULES["dentist"]
NICHE_RULES["ortho"] = NICHE_RULES["orthodontist"]
NICHE_RULES["attorney"] = NICHE_RULES["lawyer"]
NICHE_RULES["legal"] = NICHE_RULES["lawyer"]
NICHE_RULES["law firm"] = NICHE_RULES["lawyer"]
NICHE_RULES["accounting"] = NICHE_RULES["accountant"]
NICHE_RULES["tax"] = NICHE_RULES["accountant"]
NICHE_RULES["bookkeeping"] = NICHE_RULES["accountant"]
NICHE_RULES["beauty"] = NICHE_RULES["beauty salon"]
NICHE_RULES["salon"] = NICHE_RULES["beauty salon"]
NICHE_RULES["hair"] = NICHE_RULES["hair salon"]
NICHE_RULES["nails"] = NICHE_RULES["nail salon"]
NICHE_RULES["spa"] = _SPA_RULE
NICHE_RULES["wellness spa"] = _SPA_RULE
NICHE_RULES["day spa"] = _SPA_RULE
NICHE_RULES["skin clinic"] = NICHE_RULES["med spa"]

# Common service nouns / gerunds used by real buyers.
NICHE_RULES["plumbing"] = NICHE_RULES["plumber"]
NICHE_RULES["roofing"] = NICHE_RULES["roofer"]
NICHE_RULES["cleaning"] = NICHE_RULES["cleaner"]
NICHE_RULES["landscaping"] = NICHE_RULES["landscaper"]
NICHE_RULES["building"] = NICHE_RULES["builder"]
NICHE_RULES["electrical"] = NICHE_RULES["electrician"]


def is_niche_match(place: dict, business_type: str) -> bool:
    """Relevance guard for automatic Google Maps discovery.

    Keeps genuine niche businesses and rejects adjacent Maps results
    (retailers, builders returned for a plumber query, etc.).

    For every supported niche we require positive evidence in either the
    Maps category or the business name instead of trusting the search
    query alone. Unknown niches are rejected unless a meaningful niche
    token appears in the title or category, which raises precision for
    paying customers at the cost of a small recall loss.
    """
    niche = _norm_niche_text(business_type)
    title = _norm_niche_text(place.get("title"))
    category = _norm_niche_text(_place_primary_category(place))

    extra_categories = place.get("categories") or []
    if isinstance(extra_categories, str):
        extra_categories = [extra_categories]
    extra_category_text = " ".join(
        _norm_niche_text(x) for x in extra_categories
    )

    title_haystack = title
    category_haystack = f"{category} {extra_category_text}".strip()
    haystack = f"{title_haystack} {category_haystack}".strip()

    if not niche:
        return True

    # -- Retail guard ------------------------------------------------- #
    # Reject obvious retail noise, but only when the customer did not
    # actually ask for a retail-style niche.
    obvious_retail = (
        "screwfix", "toolstation", "merchant", "supplies", "supply",
        "hardware", "showroom", "store", "shop", "retail", "wholesale",
        "supermarket", "grocery",
    )
    retail_niches = (
        "florist", "bakery", "butcher", "pharmacy", "store", "shop",
        "grocer",
    )
    if not any(term in niche for term in retail_niches):
        if any(term in haystack for term in obvious_retail):
            return False

    # -- Pick the most specific matching rule ------------------------- #
    # "beauty salon" beats "beauty" because the longer key wins, so a
    # generic "salon" niche cannot accidentally borrow a specific rule.
    selected_key = None
    for key in NICHE_RULES:
        if key in niche:
            if selected_key is None or len(key) > len(selected_key):
                selected_key = key

    if selected_key:
        rule = NICHE_RULES[selected_key]

        title_match = any(
            term in title_haystack for term in rule["title_positive"]
        )
        category_match = any(
            term in category_haystack for term in rule["category_positive"]
        )
        title_conflict = any(
            term in title_haystack for term in rule["title_conflicts"]
        )

        # A named trade business ("Smith Plumbing Ltd") is trusted
        # even if Maps categories are sparse.
        if title_match:
            return True

        # A generic trading name ("A & R Services") is allowed when
        # Maps itself categorises the business in the requested trade.
        if category_match and not title_conflict:
            return True

        # Explicit conflict in the name overrides everything.
        if title_conflict:
            return False

        # Neither positive evidence nor a specific conflict. Reject
        # instead of shipping a weak lead to a paying customer.
        Actor.log.info(
            "Niche rule '%s': no positive evidence for '%s' (category: '%s').",
            selected_key,
            place.get("title") or "Unknown business",
            _place_primary_category(place) or "no category",
        )
        return False

    # -- Fallback for niches without a dedicated rule ----------------- #
    requested_tokens = {t for t in niche.split() if len(t) >= 4}
    if requested_tokens and any(t in haystack for t in requested_tokens):
        return True

    other_trade_terms = (
        "dentist", "restaurant", "pharmacy", "supermarket", "accountant",
        "solicitor", "lawyer", "estate agent", "car dealer", "hairdresser",
    )
    if any(term in haystack for term in other_trade_terms) and not any(
        term in niche for term in other_trade_terms
    ):
        return False

    # Unknown niche with no positive signal: reject by default. This is a
    # deliberate behaviour change from the previous lenient fallback,
    # because false positives are far more damaging to paid conversion
    # than a slightly narrower recall.
    return False

def apply_niche_qualification(item: dict, place: dict, business_type: str) -> dict:
    """Make commercial qualification aware of the selected business niche."""
    niche = _norm_niche_text(business_type)
    signals = item.get("signals") or {}
    primary = item.get("primaryOpportunity")
    confidence = int(item.get("confidenceScore") or 0)

    home_service = any(
        term in niche
        for term in (
            "plumber", "electrician", "roofer", "builder", "hvac",
            "heating", "air conditioning", "locksmith", "cleaner",
            "landscaper", "pest control", "handyman",
        )
    )

    if home_service and primary == "Booking conversion":
        has_form = bool(signals.get("contact_form"))
        has_call = bool(signals.get("click_to_call"))

        if not has_form:
            item["primaryOpportunity"] = "Lead capture"
            item["estimatedDealType"] = "Quote / lead capture"
            item["recommendedService"] = "Quote request and lead capture funnel"
            item["qualificationReason"] = (
                "For a home-service business, online appointment booking is not required. "
                "However, no clear contact/quote form was detected, which may create friction "
                "for visitors who want to request a quote or describe a job."
            )
            item["salesPriority"] = "HIGH" if confidence >= 90 else "MEDIUM"
            item["doNotPitch"] = confidence < 60
            item["revenueImpact"] = "HIGH"
            item["pitchHook"] = (
                f"I reviewed {item.get('businessName') or place.get('title') or 'the business'} "
                "and noticed there may be no clear online quote/contact form. A short, mobile-friendly "
                "request-a-quote flow could make it easier for high-intent visitors to become enquiries."
            )
        elif not has_call:
            item["primaryOpportunity"] = "Mobile lead capture"
            item["estimatedDealType"] = "Mobile conversion"
            item["recommendedService"] = "Click-to-call and mobile enquiry optimization"
            item["qualificationReason"] = (
                "For a home-service business, booking is not required. A contact form exists, "
                "but no click-to-call signal was detected, which may add friction for urgent mobile enquiries."
            )
            item["salesPriority"] = "MEDIUM"
            item["doNotPitch"] = confidence < 75
            item["revenueImpact"] = "HIGH"
        else:
            # Booking-only gap is not a valid sales reason for plumbers and similar trades.
            item["primaryOpportunity"] = "No strong niche-specific opportunity"
            item["estimatedDealType"] = "General website optimization"
            item["recommendedService"] = "Manual conversion review"
            item["qualificationReason"] = (
                "The only strong automated gap was missing online booking. Online booking is not "
                "a requirement for this home-service niche, and the site already exposes contact/call paths."
            )
            item["salesPriority"] = "LOW"
            item["doNotPitch"] = True
            item["revenueImpact"] = "LOW"

        name = item.get("businessName") or place.get("title") or "This business"
        item["whyThisLead"] = (
            f"{name} was evaluated using home-service conversion rules, where quote, contact, "
            "and call paths matter more than appointment booking."
        )

    appointment_niches = (
        # Health
        "dentist", "dental", "orthodont", "endodont", "periodont",
        "med spa", "medspa", "aesthetic", "botox", "filler", "skin clinic",
        # Beauty
        "beauty", "salon", "spa", "hair", "nail", "lash", "brow", "barber",
        # Legal & professional
        "lawyer", "solicitor", "attorney", "legal", "law firm",
        "accountant", "accounting", "bookkeep", "tax",
    )
    if any(term in niche for term in appointment_niches) and item.get("auditStatus") == "SUCCESS":
        name = item.get("businessName") or place.get("title") or "the business"
        niche_label = "appointment-led business"
        if any(term in niche for term in ("dentist", "dental", "orthodont", "endodont", "periodont")):
            niche_label = "dental practice"
        elif any(term in niche for term in ("med spa", "medspa", "aesthetic", "botox", "filler", "skin clinic")):
            niche_label = "aesthetics clinic"
        elif any(term in niche for term in ("beauty", "salon", "spa", "hair", "nail", "lash", "brow", "barber")):
            niche_label = "beauty business"
        elif any(term in niche for term in ("lawyer", "solicitor", "attorney", "legal", "law firm")):
            niche_label = "legal practice"
        elif any(term in niche for term in ("accountant", "accounting", "bookkeep", "tax")):
            niche_label = "accounting practice"

        booking_missing = not signals.get("booking")
        form_missing = not signals.get("contact_form")

        # Booking gap: highest-value opportunity for appointment niches.
        if primary == "Booking conversion" and booking_missing:
            item["whyThisLead"] = (
                f"{name} was evaluated as a {niche_label}, where a clear online "
                "booking or consultation path is a high-value conversion opportunity. "
                "The audit found no clear path across the pages checked, giving a concrete "
                "reason to reach out rather than a generic website pitch."
            )
            item["salesPriority"] = "HIGH" if confidence >= 90 else "MEDIUM"
            item["doNotPitch"] = confidence < 75
            item["estimatedDealType"] = "Booking funnel"
            item["recommendedService"] = "Online booking funnel implementation"
            item["revenueImpact"] = "HIGH"
            item["qualificationReason"] = (
                "No clear online booking path was detected for an appointment-led business. "
                "That creates a concrete conversion opportunity, provided the audit confidence "
                "is sufficient for outreach."
            )

            if any(term in niche for term in ("dentist", "dental", "orthodont", "endodont", "periodont")):
                item["pitchHook"] = (
                    f"I reviewed {name} and couldn't find a clear online appointment path. "
                    "Patients often research practices outside reception hours, so a simple booking flow "
                    "could capture demand that would otherwise wait or move to another clinic."
                )
            elif any(term in niche for term in ("med spa", "medspa", "aesthetic", "botox", "filler", "skin clinic", "beauty", "salon", "spa", "hair", "nail", "lash", "brow", "barber")):
                item["pitchHook"] = (
                    f"I reviewed {name} and couldn't find a clear online booking path. "
                    "For beauty and aesthetics businesses, letting clients book while intent is high can "
                    "turn social and search traffic into appointments without waiting for a reply."
                )
            elif any(term in niche for term in ("lawyer", "solicitor", "attorney", "legal", "law firm")):
                item["pitchHook"] = (
                    f"I reviewed {name} and noticed there may be no clear consultation-request path. "
                    "A short, confidential enquiry flow can reduce friction for people who need legal help "
                    "but are not ready to call immediately."
                )
            elif any(term in niche for term in ("accountant", "accounting", "bookkeep", "tax")):
                item["pitchHook"] = (
                    f"I reviewed {name} and noticed there may be no clear consultation or enquiry path. "
                    "A focused lead form for tax, bookkeeping or advisory enquiries could make it easier "
                    "to convert high-intent visitors into qualified conversations."
                )

        # Lead-capture gap: booking path may exist, but enquiry form is missing.
        elif primary == "Lead capture" and form_missing:
            item["whyThisLead"] = (
                f"{name} was evaluated as a {niche_label}, where capturing enquiry "
                "intent online is a high-value conversion path. The audit did not detect "
                "a clear contact or enquiry form across the pages checked."
            )
            item["salesPriority"] = "HIGH" if confidence >= 90 else "MEDIUM"
            item["doNotPitch"] = confidence < 75
            item["estimatedDealType"] = "Lead capture"
            item["recommendedService"] = "Enquiry / lead capture form implementation"
            item["revenueImpact"] = "HIGH"
            item["qualificationReason"] = (
                "The appointment-led business has no clear online enquiry or contact form "
                "detected. That creates a concrete opportunity to capture high-intent visitors "
                "who are not ready to call."
            )

            if any(term in niche for term in ("dentist", "dental", "orthodont", "endodont", "periodont")):
                item["pitchHook"] = (
                    f"I reviewed {name} and couldn't find a clear online enquiry form for patients "
                    "who aren't ready to book yet. A short, low-friction contact path can capture "
                    "questions that currently never turn into a call."
                )
            elif any(term in niche for term in ("med spa", "medspa", "aesthetic", "botox", "filler", "skin clinic", "beauty", "salon", "spa", "hair", "nail", "lash", "brow", "barber")):
                item["pitchHook"] = (
                    f"I reviewed {name} and couldn't find a clear enquiry form for clients who aren't "
                    "ready to book immediately. That kind of soft enquiry path is often where "
                    "consultations and higher-value treatments actually start."
                )
            elif any(term in niche for term in ("lawyer", "solicitor", "attorney", "legal", "law firm")):
                item["pitchHook"] = (
                    f"I reviewed {name} and noticed there may be no clear confidential enquiry form. "
                    "Many legal prospects want to describe their situation before calling, so a short "
                    "intake form can qualify high-value enquiries earlier."
                )
            elif any(term in niche for term in ("accountant", "accounting", "bookkeep", "tax")):
                item["pitchHook"] = (
                    f"I reviewed {name} and noticed there may be no clear enquiry form for tax, "
                    "bookkeeping or advisory questions. A short intake form is often what turns "
                    "a curious visitor into a qualified conversation."
                )
    return item


def enrich_with_map_data(
    item: dict,
    place: dict,
    city: str,
    business_type: str,
) -> dict:

    map_name = place.get("title")

    if map_name:
        # Google Maps is the canonical business-name source in automatic mode.
        item["businessName"] = map_name

        pages_scanned = item.get("pagesScanned") or 0
        primary = item.get("primaryOpportunity") or "digital conversion"
        gap_text = ""
        gaps = item.get("gaps") or []
        if gaps:
            gap_text = str(gaps[0]).rstrip(".")

        if item.get("auditStatus") == "SUCCESS":
            item["whyThisLead"] = (
                f"{map_name} has an active public website, but the automated audit "
                f"found a specific {str(primary).lower()} opportunity after checking "
                f"{pages_scanned} page(s). This gives an agency a concrete reason to "
                f"approach the business instead of sending a generic website pitch."
            )

            if gap_text:
                item["pitchHook"] = (
                    f"I reviewed {map_name} and noticed a potential conversion gap: "
                    f"{gap_text}. There may be an opportunity to improve the path from "
                    f"website visitor to enquiry or booked appointment. I can show you "
                    f"the exact change I would test first."
                )

    map_phone = place.get("phone")

    if map_phone and map_phone not in item.get("phones", []):
        item.setdefault("phones", []).append(map_phone)

    item["city"] = city
    item["businessType"] = business_type
    item["mapAddress"] = place.get("address")
    item["mapPhone"] = map_phone
    item["mapCategory"] = _place_primary_category(place)
    item["mapRating"] = place.get("totalScore")
    item["mapReviewsCount"] = place.get("reviewsCount")
    item["mapPlaceId"] = place.get("placeId")
    item["openingHours"] = (
        place.get("openingHours")
        or place.get("openingHoursStructured")
        or place.get("openingHoursDetailed")
    )

    return item

def is_commercially_qualified(
    item: dict,
    min_score: int,
) -> bool:

    return (
        item.get(
            "auditStatus"
        )
        in (
            "SUCCESS",
            "NO_WEBSITE",
            "NO_WEBSITE_LINKED",
        )

        and item.get(
            "opportunityScore",
            0,
        )
        >= min_score

        and item.get(
            "confidenceScore",
            0,
        )
        >= 60

        and not item.get(
            "doNotPitch",
            True,
        )

        and item.get(
            "salesPriority"
        )
        in (
            "HIGH",
            "MEDIUM",
        )

        and item.get(
            "estimatedDealType"
        )
        not in (
            "Tracking setup",
            "Meta Ads tracking",
            "SEO metadata",
            "Live chat",
            "Manual review",
        )
    )


def make_public_output(
    item: dict,
) -> dict:
    """Return the buyer-facing LeadGap record in a clean, useful order.

    Internal audit fields stay inside the Actor logic and are intentionally
    excluded from the public Dataset so customers see sales-ready leads rather
    than debugging data.
    """

    map_phone = item.get("mapPhone")
    phones = item.get("phones") or []

    if map_phone:
        phone = map_phone
    elif isinstance(phones, list) and phones:
        phone = phones[0]
    else:
        phone = None

    return {
        "businessName": item.get("businessName"),
        "businessType": item.get("businessType"),
        "city": item.get("city"),
        "country": item.get("country"),

        "website": item.get("website"),
        "websiteSource": item.get("websiteSource"),
        "phone": phone,
        "emails": item.get("emails") or [],
        "facebook": item.get("facebook"),
        "instagram": item.get("instagram"),
        "openingHours": item.get("openingHours"),

        "rating": item.get("mapRating"),
        "reviews": item.get("mapReviewsCount"),

        "salesPriority": item.get("salesPriority"),
        "confidence": item.get("confidence"),
        "confidenceScore": item.get("confidenceScore"),
        "opportunityScore": item.get("opportunityScore"),

        "primaryOpportunity": item.get("primaryOpportunity"),
        "estimatedDealType": item.get("estimatedDealType"),
        "recommendedService": item.get("recommendedService"),
        "revenueImpact": item.get("revenueImpact"),

        "whyThisLead": item.get("whyThisLead"),
        "pitchHook": item.get("pitchHook"),
        "qualificationReason": item.get("qualificationReason"),

        "auditStatus": item.get("auditStatus"),
        "cms": item.get("cms"),
        "pagesScanned": item.get("pagesScanned"),

        "mapAddress": item.get("mapAddress"),
        "mapCategory": item.get("mapCategory"),
        "mapPlaceId": item.get("mapPlaceId"),
    }


def log_place_diagnostic(
    place: dict,
    niche_match: bool,
    item: dict | None = None,
    commercially_qualified: bool | None = None,
    pushed: bool | None = None,
    skip_reason: str | None = None,
    website: str | None = None,
) -> None:
    """Emit one compact machine-readable diagnostic line per discovered place."""
    item = item or {}
    signals = item.get("signals") or {}
    payload = {
        "title": place.get("title"),
        "category": _place_primary_category(place),
        "placeId": place.get("placeId"),
        "nicheMatch": niche_match,
        "auditStatus": item.get("auditStatus"),
        "booking": signals.get("booking"),
        "contactForm": signals.get("contact_form"),
        "cta": signals.get("cta"),
        "clickToCall": signals.get("click_to_call"),
        "primaryOpportunity": item.get("primaryOpportunity"),
        "confidenceScore": item.get("confidenceScore"),
        "salesPriority": item.get("salesPriority"),
        "doNotPitch": item.get("doNotPitch"),
        "websiteSource": item.get("websiteSource"),
        "externalWebsiteCheck": item.get("externalWebsiteCheck"),
        "commerciallyQualified": commercially_qualified,
        "pushed": pushed,
        "skipReason": skip_reason,
        "website": website or item.get("website"),
    }
    Actor.log.info("PLACE_DIAG %s", json.dumps(payload, ensure_ascii=False, default=str))


async def push_qualified(
    item: dict,
) -> tuple[bool, bool]:
    """Push one paid result and report (item_written, charge_limit_reached)."""
    try:
        charge_result = await Actor.push_data(
            make_public_output(item),
            charged_event_name="qualified-opportunity",
        )
    except Exception as exc:
        Actor.log.warning("push_data failed; result was not confirmed written: %s", exc)
        return False, False

    # Local/non-PPE execution may return None while still writing the item.
    if charge_result is None:
        return True, False

    charged_count = int(getattr(charge_result, "charged_count", 0) or 0)
    limit_reached = bool(
        getattr(charge_result, "event_charge_limit_reached", False)
    )

    # Apify caps both charging and dataset pushing when the PPE limit is hit.
    # Therefore charged_count is the safest signal that this paid item was
    # actually accepted; do not increment maxResults for a capped item.
    return charged_count >= 1, limit_reached


async def main() -> None:

    async with Actor:

        actor_input = (
            await Actor.get_input()
            or {}
        )


        country = (
            actor_input.get(
                "country",
                "UK",
            )
        )


        city = (
            actor_input.get(
                "city",
                "",
            )
            or ""
        ).strip()


        business_type = (
            actor_input.get(
                "businessType",
                "",
            )
            or ""
        ).strip()


        manual_urls = (
            actor_input.get(
                "websites",
                [],
            )
            or []
        )


        max_businesses = int(
            actor_input.get(
                "maxBusinesses",
                30,
            )
        )


        min_score = int(
            actor_input.get(
                "minOpportunityScore",
                0,
            )
        )


        max_results = int(
            actor_input.get(
                "maxResults",
                25,
            )
        )


        if country not in SUPPORTED:

            raise ValueError(
                f"Unsupported country: {country}"
            )


        timeout = httpx.Timeout(
            20.0,
            connect=10.0,
        )


        headers = {
            "Accept-Language": ACCEPT_LANGUAGE[country],
            "User-Agent": (
                "Mozilla/5.0 "
                "(Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 "
                "(KHTML, like Gecko) "
                "Chrome/124.0 Safari/537.36"
            )
        }


        qualified = 0
        stats = {
            "discovered": 0,
            "after_dedup": 0,
            "after_relevance": 0,
            "after_commercial_eval": 0,
            "qualified": 0,
            "pushed": 0,
            "FOUND": 0,
            "NOT_FOUND": 0,
            "UNAVAILABLE": 0,
        }


        async with httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
        ) as client:


            # MANUAL MODE

            if manual_urls:

                Actor.log.info(
                    "Running in manual website audit mode."
                )


                for raw_url in manual_urls:

                    if qualified >= max_results:
                        break


                    item = await audit(
                        client,
                        raw_url,
                        country,
                    )
                    stats["after_commercial_eval"] += 1

                    commercially_qualified = is_commercially_qualified(
                        item,
                        min_score,
                    )
                    Actor.log.info(
                        "MANUAL_DIAG %s",
                        json.dumps({
                            "website": item.get("website"),
                            "auditStatus": item.get("auditStatus"),
                            "primaryOpportunity": item.get("primaryOpportunity"),
                            "confidenceScore": item.get("confidenceScore"),
                            "salesPriority": item.get("salesPriority"),
                            "doNotPitch": item.get("doNotPitch"),
                            "commerciallyQualified": commercially_qualified,
                        }, ensure_ascii=False, default=str),
                    )

                    if commercially_qualified:
                        stats["qualified"] += 1
                        pushed, charge_limit_reached = await push_qualified(item)
                        if pushed:
                            qualified += 1
                            stats["pushed"] += 1
                        if charge_limit_reached:
                            Actor.log.info(
                                "Pay-per-event charge limit reached; stopping before extra work."
                            )
                            break


            # AUTOMATIC LEAD FINDER MODE

            else:

                if not city:

                    raise ValueError(
                        "Add a city for automatic discovery."
                    )


                if not business_type:

                    raise ValueError(
                        "Add a business type "
                        "for automatic discovery."
                    )


                places = await discover_businesses(
                    country=country,
                    city=city,
                    business_type=business_type,
                    max_businesses=max_businesses,
                )
                stats["discovered"] = len(places)
                for discovered_place in places:
                    Actor.log.info(
                        "PLACE_INPUT %s",
                        json.dumps({
                            "title": discovered_place.get("title"),
                            "category": _place_primary_category(discovered_place),
                            "placeId": discovered_place.get("placeId"),
                            "website": discovered_place.get("website"),
                        }, ensure_ascii=False, default=str),
                    )
                if places:
                    Actor.log.info(
                        "MAPS_FIRST_PLACE %s",
                        json.dumps(places[0], ensure_ascii=False, default=str),
                    )

                # Remove duplicate Google Maps listings before auditing.
                # This prevents one real business from being sold as two leads.
                places = deduplicate_places(places)
                stats["after_dedup"] = len(places)


                seen_websites = set()
                seen_place_ids = set()


                for place in places:

                    niche_match = is_niche_match(place, business_type)
                    if not niche_match:
                        log_place_diagnostic(place, niche_match=False)
                        continue

                    stats["after_relevance"] += 1

                    if qualified >= max_results:
                        break


                    place_id = (
                        place.get("placeId")
                    )


                    if (
                        place_id
                        and place_id in seen_place_ids
                    ):
                        log_place_diagnostic(
                            place,
                            niche_match=True,
                            skip_reason="SEEN_PLACE_ID",
                        )
                        continue


                    if place_id:
                        seen_place_ids.add(
                            place_id
                        )


                    website = (
                        place.get("website")
                        or ""
                    ).strip()


                    # No website linked in Maps -> verify externally first.

                    if not website:

                        verification = await find_external_business_website(
                            client=client,
                            place=place,
                            city=city,
                        )
                        verification_status = verification.get("status")
                        if verification_status in ("FOUND", "NOT_FOUND", "UNAVAILABLE"):
                            stats[verification_status] += 1

                        external_website = (
                            verification.get("website")
                            or ""
                        ).strip()

                        if external_website:

                            website_key = _website_identity_key(
                                external_website
                            )

                            if (
                                website_key
                                and website_key in seen_websites
                            ):
                                log_place_diagnostic(
                                    place,
                                    niche_match=True,
                                    skip_reason="SEEN_WEBSITE",
                                    website=website_key,
                                )
                                continue

                            if website_key:
                                seen_websites.add(
                                    website_key
                                )

                            Actor.log.info(
                                "External website found for %s: %s",
                                place.get("title") or "Unknown business",
                                external_website,
                            )

                            item = await audit(
                                client,
                                external_website,
                                country,
                            )

                            item = enrich_with_map_data(
                                item=item,
                                place=place,
                                city=city,
                                business_type=business_type,
                            )

                            item = apply_niche_qualification(
                                item=item,
                                place=place,
                                business_type=business_type,
                            )

                            item["externalWebsiteCheck"] = "FOUND"
                            item["externalWebsiteEvidence"] = verification.get(
                                "evidence"
                            )
                            item["websiteSource"] = "EXTERNAL_SEARCH"

                        else:

                            item = make_no_website_lead(
                                place=place,
                                country=country,
                                city=city,
                                business_type=business_type,
                                verification=verification,
                            )


                    # Website exists -> full audit

                    else:

                        normalized = normalize_url(
                            website
                        )


                        website_key = _website_identity_key(
                            normalized
                        )


                        if (
                            website_key
                            and website_key in seen_websites
                        ):
                            log_place_diagnostic(
                                place,
                                niche_match=True,
                                skip_reason="SEEN_WEBSITE",
                                website=website_key,
                            )
                            continue


                        if website_key:
                            seen_websites.add(
                                website_key
                            )


                        item = await audit(
                            client,
                            normalized,
                            country,
                        )


                        item = enrich_with_map_data(
                            item=item,
                            place=place,
                            city=city,
                            business_type=business_type,
                        )

                        item = apply_niche_qualification(
                            item=item,
                            place=place,
                            business_type=business_type,
                        )

                        item["websiteSource"] = "GOOGLE_MAPS"


                    stats["after_commercial_eval"] += 1
                    commercially_qualified = is_commercially_qualified(
                        item,
                        min_score,
                    )
                    if commercially_qualified:
                        stats["qualified"] += 1
                        pushed, charge_limit_reached = await push_qualified(item)
                        log_place_diagnostic(
                            place,
                            niche_match=True,
                            item=item,
                            commercially_qualified=True,
                            pushed=pushed,
                        )
                        if pushed:
                            qualified += 1
                            stats["pushed"] += 1
                        if charge_limit_reached:
                            Actor.log.info(
                                "Pay-per-event charge limit reached; stopping before extra work."
                            )
                            break
                    else:
                        log_place_diagnostic(
                            place,
                            niche_match=True,
                            item=item,
                            commercially_qualified=False,
                            pushed=False,
                        )


        Actor.log.info(
            "RUN_SUMMARY %s",
            json.dumps(stats, ensure_ascii=False, sort_keys=True),
        )
        Actor.log.info(
            "Finished. Qualified opportunities pushed: %s",
            qualified,
        )


if __name__ == "__main__":
    asyncio.run(main())