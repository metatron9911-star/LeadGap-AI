import sys, types

# Minimal stubs so pure helper tests can import main.py without the Apify SDK installed.
apify = types.ModuleType("apify")
class _Log:
    def info(self, *a, **k): pass
    def warning(self, *a, **k): pass
class _Actor:
    log = _Log()
apify.Actor = _Actor
sys.modules["apify"] = apify

apify_client = types.ModuleType("apify_client")
class ApifyClientAsync: pass
apify_client.ApifyClientAsync = ApifyClientAsync
sys.modules["apify_client"] = apify_client

from main import has_contact_form, PATTERNS, apply_niche_qualification, is_niche_match, find_external_business_website, _place_primary_category, _website_identity_key, _blocked_discovery_domain, _is_public_contact_email, _strip_tracking_params, confidence_for_pages, _sanitize_contact_emails, _business_domain_affinity, _business_email_affinity, _compose_grounded_niche_pitch_hook, _same_domain_location_filter, is_needs_review_candidate
import re
import asyncio

# Contact-form localization
DE_FORM = '''
<form class="kontakt" action="/senden">
  <label for="telefon">Telefon</label>
  <input id="telefon" name="telefon" type="text">
  <label for="nachricht">Nachricht</label>
  <textarea id="nachricht" name="nachricht"></textarea>
</form>
'''
PL_FORM = '''
<form class="zapytanie" action="/wyslij">
  <input name="imie" placeholder="Imię">
  <input name="email" placeholder="Email">
</form>
'''
IT_FORM = '''
<form class="richiesta-preventivo" action="/invia">
  <input name="telefono" placeholder="Telefono">
</form>
'''
ES_FORM = '''
<form class="contacto" action="/enviar">
  <input name="correo" placeholder="Correo">
</form>
'''
assert has_contact_form(DE_FORM), 'German form not detected'
assert has_contact_form(PL_FORM), 'Polish form not detected'
assert has_contact_form(IT_FORM), 'Italian form not detected'
assert has_contact_form(ES_FORM), 'Spanish form not detected'

# Booking localization
cases = {
    'NL appointment': 'Maak een afspraak online',
    'NL reserve': 'Reserveren',
    'IT': 'Prenotare una visita',
    'IT plural': 'Prenotazioni online',
    'PL visit': 'Umów wizytę',
    'PL signup': 'Zapisz się online',
    'DE': 'Termin vereinbaren',
    'FR': 'Prendre rendez-vous',
    'ES': 'Reservar cita',
}
for label, text in cases.items():
    assert re.search(PATTERNS['booking'], text, re.I), f'{label} failed: {text}'


# Niche aliases + retail guard
assert is_niche_match(
    {"title": "Bright Smile Dental", "category": "Dentist"},
    "Dentist",
), "canonical Dentist failed"
assert is_niche_match(
    {"title": "Bright Smile Dental", "category": "Dentist"},
    "Dental",
), "alias Dental failed"
assert _place_primary_category(
    {"title": "Bright Smile Dental", "categoryName": "Dentist", "categories": ["Dentist"]}
) == "Dentist", "categoryName fallback failed"
assert _website_identity_key("https://www.bupa.co.uk/dental/a/?utm_source=x") != _website_identity_key("https://www.bupa.co.uk/dental/b/"), "shared-domain location pages must remain distinct"
assert _website_identity_key("https://example.com/?utm_source=x") == _website_identity_key("https://www.example.com/"), "root URLs should dedupe by host"
assert _blocked_discovery_domain("https://dentist-london.com/practice/example/"), "dentist-london directory must be blocked"
assert _blocked_discovery_domain("https://www.dental-art.co.uk/example"), "dental-art directory must be blocked"
assert _blocked_discovery_domain("https://dentistlocator.co.uk/dentists/london/example/"), "dentistlocator directory must be blocked"
assert is_niche_match(
    {"title": "Smith & Jones Law", "category": "Lawyer"},
    "Legal",
), "alias Legal failed"
assert is_niche_match(
    {"title": "Pink Rose Beauty", "category": "Beauty salon"},
    "Salon",
), "alias Salon failed"
assert not is_niche_match(
    {"title": "Screwfix Bristol", "category": "Hardware store"},
    "Plumber",
), "retail guard failed"
assert is_niche_match(
    {"title": "Selsdon Smiles Dental Practice", "category": "Dentist", "categories": ["Dentist", "Dental clinic", "Dental supply store"]},
    "Dentist",
), "secondary retail category must not reject a genuine dentist"

# Common service-form aliases must resolve to canonical niche rules.
assert is_niche_match(
    {"title": "Smith Plumbers Ltd", "category": "Plumber"},
    "Plumbing",
), "alias Plumbing failed"
assert is_niche_match(
    {"title": "Acme Roofers", "category": "Roofer"},
    "Roofing",
), "alias Roofing failed"
assert is_niche_match(
    {"title": "Sparkle Services", "category": "Cleaning service"},
    "Cleaning",
), "alias Cleaning failed"
assert is_niche_match(
    {"title": "Green Gardens", "category": "Landscaper"},
    "Landscaping",
), "alias Landscaping failed"
assert is_niche_match(
    {"title": "ABC Construction", "category": "Builder"},
    "Building",
), "alias Building failed"
assert is_niche_match(
    {"title": "Volt Works", "category": "Electrician"},
    "Electrical",
), "alias Electrical failed"

# General spa must not be forced through medical-aesthetics relevance.
assert is_niche_match(
    {"title": "Lotus Wellness Spa", "category": "Day spa"},
    "Spa",
), "general Spa alias failed"

# Appointment lead-capture copy: booking exists, form missing.
item = {
    'auditStatus': 'SUCCESS',
    'businessName': 'Bright Smile Dental',
    'signals': {'booking': True, 'contact_form': False},
    'primaryOpportunity': 'Lead capture',
    'confidenceScore': 90,
    'salesPriority': 'MEDIUM',
    'doNotPitch': False,
    'estimatedDealType': 'Generic',
    'recommendedService': 'Generic',
    'revenueImpact': 'MEDIUM',
    'whyThisLead': 'generic',
    'pitchHook': 'generic',
}
place = {'title': 'Bright Smile Dental'}
out = apply_niche_qualification(item, place, 'Dental')
assert out['salesPriority'] == 'HIGH'
assert out['estimatedDealType'] == 'Lead capture'
assert 'dental practice' in out['whyThisLead']
assert 'enquiry form' in out['pitchHook']


# External search must distinguish challenge/empty pages from a genuine NOT_FOUND result.
class _FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text

class _FakeClient:
    def __init__(self, response):
        self.response = response
    async def get(self, *args, **kwargs):
        return self.response

async def _test_external_search_statuses():
    place = {"title": "Bright Smile Dental", "address": "1 King St, Manchester"}

    out_202 = await find_external_business_website(
        _FakeClient(_FakeResponse(202, "<html>challenge</html>")),
        place,
        "Manchester",
    )
    assert out_202["status"] == "UNAVAILABLE", out_202

    out_empty = await find_external_business_website(
        _FakeClient(_FakeResponse(200, "<html><body>No results markup</body></html>")),
        place,
        "Manchester",
    )
    assert out_empty["status"] == "UNAVAILABLE", out_empty

    weak_result_html = """
    <div class="result">
      <a class="result__a" href="https://example.org/other">Unrelated Directory</a>
      <div class="result__snippet">Something else in London</div>
    </div>
    """
    out_weak = await find_external_business_website(
        _FakeClient(_FakeResponse(200, weak_result_html)),
        place,
        "Manchester",
    )
    assert out_weak["status"] == "NOT_FOUND", out_weak
    directory_result_html = """
    <div class="result">
      <a class="result__a" href="https://dental-directory.example/riverside-dental-centre">
        Riverside Dental Centre
      </a>
      <div class="result__snippet">Riverside Dental Centre in Manchester - local dentist profile</div>
    </div>
    """
    out_directory = await find_external_business_website(
        _FakeClient(_FakeResponse(200, directory_result_html)),
        {"title": "Riverside Dental Centre", "address": "1 River St, Manchester M1 1AA"},
        "Manchester",
    )
    assert out_directory["status"] == "NOT_FOUND", out_directory

asyncio.run(_test_external_search_statuses())

print('All smoke tests passed')

# Sellable-v1 production hygiene regressions.
assert not _is_public_contact_email("8c4075d5481d476e945486754f783364@sentry.io")
assert not _is_public_contact_email("2062d0a4929b45348643784b5cb39c36@sentry.wixpress.com")
assert not _is_public_contact_email("best-new-practice-1@2x.png")
assert _is_public_contact_email("reception@royalarsenaldentists.com")
assert _strip_tracking_params("https://example.com/page?utm_source=google&utm_medium=organic") == "https://example.com/page"
assert _strip_tracking_params("https://example.com/page?id=7&utm_source=google") == "https://example.com/page?id=7"
low_conf = confidence_for_pages(1, signals={"title": True, "meta_description": True, "mobile_viewport": True}, successful_fetches=1, attempted_fetches=1, contacts_found=True)[1]
assert low_conf < 60, low_conf

# Email hygiene: placeholders and cross-location contamination.
cleaned, placeholders, cross, dropped = _sanitize_contact_emails(
    ["example@email.com", "info@keppeladvanceddentistry.co.uk"],
    "https://keppeladvanceddentistry.co.uk/",
    "Keppel Advanced Dentistry",
)
assert cleaned == ["info@keppeladvanceddentistry.co.uk"], cleaned
assert placeholders == 1 and cross == 0, (placeholders, cross)
assert dropped["placeholder"] == ["example@email.com"], dropped
assert dropped["cross_location"] == [], dropped

cleaned, placeholders, cross, dropped = _sanitize_contact_emails(
    ["reception@albiondentalbrighton.co.uk", "reception@crosswaysdental.co.uk"],
    "https://www.qualitydentalgroup.co.uk/coulsdon/about-us/",
    "Crossways Dental Coulsdon",
)
assert cleaned == ["reception@crosswaysdental.co.uk"], cleaned
assert placeholders == 0 and cross == 1, (placeholders, cross)
assert dropped["placeholder"] == [], dropped
assert dropped["cross_location"] == ["reception@albiondentalbrighton.co.uk"], dropped

cleaned, placeholders, cross, dropped = _sanitize_contact_emails(
    ["hello@72dental.co.uk"],
    "https://72dentalcoulsdon.co.uk/",
    "72 Dental",
)
assert cleaned == ["hello@72dental.co.uk"], cleaned
assert placeholders == 0 and cross == 0, (placeholders, cross)
assert dropped == {
    "placeholder": [],
    "cross_location": [],
    "same_domain_location": [],
}, dropped

# Industry-generic token "dental" alone must never establish affinity.
assert not _business_domain_affinity(
    "albiondentalbrighton.co.uk",
    "Crossways Dental Coulsdon",
)
assert _business_domain_affinity(
    "crooklogdental.co.uk",
    "Crook Log Dental Practice",
)
assert _business_domain_affinity(
    "72dental.co.uk",
    "72 Dental",
)

# Cross-domain identity can also be carried by the local part.
assert _business_email_affinity(
    "mulgravedentalcentre17@gmail.com",
    "Mulgrave Dental Centre",
)
assert _business_email_affinity(
    "bluedental79@gmail.com",
    "Bluedental - Dentist Croydon - Emergency Dentist",
)
assert _business_email_affinity(
    "thewhitehouse@soegateway.com",
    "The White House Dental Surgery",
)
assert not _business_email_affinity(
    "reception@albiondentalbrighton.co.uk",
    "Crossways Dental Coulsdon",
)

cleaned, placeholders, cross, dropped = _sanitize_contact_emails(
    ["mulgravedentalcentre17@gmail.com"],
    "https://www.mulgravedental.com/",
    "Mulgrave Dental Centre",
)
assert cleaned == ["mulgravedentalcentre17@gmail.com"], cleaned
assert placeholders == 0 and cross == 0, (placeholders, cross)

cleaned, placeholders, cross, dropped = _sanitize_contact_emails(
    ["your.email@example.com", "hello@confidentalclinic.com"],
    "https://confidentalclinic.com/purley",
    "ConfiDental Clinic Purley",
)
assert cleaned == ["hello@confidentalclinic.com"], cleaned
assert placeholders == 1 and cross == 0, (placeholders, cross)
assert dropped["placeholder"] == ["your.email@example.com"], dropped

cleaned, placeholders, cross, dropped = _sanitize_contact_emails(
    ["info@example.com", "reception@abbeywooddental.co.uk"],
    "https://abbeywooddental.co.uk/",
    "Abbeywood Dental",
)
assert cleaned == ["reception@abbeywooddental.co.uk"], cleaned
assert placeholders == 1 and cross == 0, (placeholders, cross)
assert dropped["placeholder"] == ["info@example.com"], dropped
assert dropped["cross_location"] == [], dropped

# Final pitch-hook architecture: one writer, grounded by gap + niche + evidence.
dental_item = {
    "auditStatus": "SUCCESS",
    "businessName": "Bright Smile Dental",
    "primaryOpportunity": "Lead capture",
    "gaps": ["No contact form detected"],
}
dental_hook = _compose_grounded_niche_pitch_hook(
    dental_item,
    {"title": "Bright Smile Dental"},
    "Dentist",
)
assert "No contact form detected" in dental_hook
assert "dental practice" in dental_hook
assert "patients" in dental_hook.lower()
assert "enquiry form" in dental_hook.lower()
assert "appointment-led business has no clear online" not in dental_hook.lower()
assert "couldn't find a clear online enquiry form" not in dental_hook.lower()

legal_item = {
    "auditStatus": "SUCCESS",
    "businessName": "Smith Legal",
    "primaryOpportunity": "Lead capture",
    "gaps": ["No contact form detected"],
}
legal_hook = _compose_grounded_niche_pitch_hook(
    legal_item,
    {"title": "Smith Legal"},
    "Legal",
)
assert "No contact form detected" in legal_hook
assert "legal practice" in legal_hook
assert "prospective clients" in legal_hook.lower()
assert "patients" not in legal_hook.lower()
assert "dental practice" not in legal_hook.lower()
assert legal_hook != dental_hook

booking_item = {
    "auditStatus": "SUCCESS",
    "businessName": "Bright Smile Dental",
    "primaryOpportunity": "Booking conversion",
    "gaps": ["No booking path detected"],
}
booking_hook = _compose_grounded_niche_pitch_hook(
    booking_item,
    {"title": "Bright Smile Dental"},
    "Dentist",
)
assert "No booking path detected" in booking_hook
assert "booking or consultation path" in booking_hook
assert "patients" in booking_hook.lower()
assert "enquiry form" not in booking_hook.lower()
assert booking_hook != dental_hook

paid_social_item = {
    "auditStatus": "SUCCESS",
    "businessName": "Bright Smile Dental",
    "primaryOpportunity": "Paid social measurement",
    "gaps": ["No Meta Pixel detected"],
}
paid_social_hook = _compose_grounded_niche_pitch_hook(
    paid_social_item,
    {"title": "Bright Smile Dental"},
    "Dentist",
)
assert "paid social measurement" in paid_social_hook.lower()
assert "No Meta Pixel detected" in paid_social_hook
assert "dental practice" in paid_social_hook

after_hours_item = {
    "auditStatus": "SUCCESS",
    "businessName": "Bright Smile Dental",
    "primaryOpportunity": "After-hours enquiry capture",
    "gaps": ["No live-chat technology detected"],
}
after_hours_hook = _compose_grounded_niche_pitch_hook(
    after_hours_item,
    {"title": "Bright Smile Dental"},
    "Dentist",
)
assert "after-hours enquiry capture" in after_hours_hook.lower()
assert "No live-chat technology detected" in after_hours_hook
assert "dental practice" in after_hours_hook
assert after_hours_hook != paid_social_hook

# Same-domain sibling branch filtering: conservative, Maps-grounded.
sky_place = {
    "title": "Sky Dental Clinic Bexley",
    "address": "Bexley, Greater London, United Kingdom",
    "city": "Bexley",
    "neighborhood": None,
    "street": "High Street",
    "postalCode": "DA5",
}
cleaned, dropped = _same_domain_location_filter(
    [
        "beckenham@skydentalclinic.co.uk",
        "bexley@skydentalclinic.co.uk",
        "orpington@skydentalclinic.co.uk",
    ],
    "Sky Dental Clinic Bexley",
    sky_place,
)
assert cleaned == ["bexley@skydentalclinic.co.uk"], cleaned
assert dropped == [
    "beckenham@skydentalclinic.co.uk",
    "orpington@skydentalclinic.co.uk",
], dropped

# Generic inboxes remain even when branch-specific siblings are filtered.
cleaned, dropped = _same_domain_location_filter(
    [
        "info@skydentalclinic.co.uk",
        "bexley@skydentalclinic.co.uk",
        "orpington@skydentalclinic.co.uk",
    ],
    "Sky Dental Clinic Bexley",
    sky_place,
)
assert cleaned == [
    "bexley@skydentalclinic.co.uk",
    "info@skydentalclinic.co.uk",
], cleaned
assert dropped == ["orpington@skydentalclinic.co.uk"], dropped

# No positive location match => preserve everything.
cleaned, dropped = _same_domain_location_filter(
    ["beckenham@example.co.uk", "orpington@example.co.uk"],
    "Example Dental Bexley",
    sky_place,
)
assert cleaned == ["beckenham@example.co.uk", "orpington@example.co.uk"], cleaned
assert dropped == [], dropped

# Single email => never filter.
cleaned, dropped = _same_domain_location_filter(
    ["reception@crosswaysdental.co.uk"],
    "Crossways Dental Coulsdon",
    {"address": "Coulsdon, UK", "city": "Coulsdon"},
)
assert cleaned == ["reception@crosswaysdental.co.uk"], cleaned
assert dropped == [], dropped

# Needs-review classification
review_ok = {
    "auditStatus": "SUCCESS",
    "opportunityScore": 83,
    "confidenceScore": 59,
    "pagesScanned": 1,
    "salesPriority": "MEDIUM",
    "estimatedDealType": "Booking funnel",
}
review_low_score = dict(review_ok); review_low_score["opportunityScore"] = 20
review_high_conf = dict(review_ok); review_high_conf["confidenceScore"] = 95
review_two_pages = dict(review_ok); review_two_pages["pagesScanned"] = 2
review_tracking = dict(review_ok); review_tracking["estimatedDealType"] = "Meta Ads tracking"
assert is_needs_review_candidate(review_ok, 0)
assert not is_needs_review_candidate(review_low_score, 0)
assert not is_needs_review_candidate(review_high_conf, 0)
assert not is_needs_review_candidate(review_two_pages, 0)
assert not is_needs_review_candidate(review_tracking, 0)
assert not is_needs_review_candidate(review_ok, 90)
