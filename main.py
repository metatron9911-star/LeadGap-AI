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
    url = (url or "")