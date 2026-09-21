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

from main import has_contact_form, PATTERNS, apply_niche_qualification, is_niche_match, find_external_business_website, _place_primary_category
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
