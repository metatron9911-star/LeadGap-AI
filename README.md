# LeadGap AI — Local Business Leads You Can Actually Sell To

**Stop exporting directories. Start closing deals.**

LeadGap AI finds local businesses, audits their websites, and returns only the
ones with a real, provable sales angle — plus the exact pitch to use.

---

## The problem every agency knows

You already know how to find local businesses. Google Maps gives you thousands.

The hard part is:

- **Which one is worth your time?**
- **What do you actually say when you call them?**
- **Why should they care — today, not "someday"?**

Manual qualification can take substantial research per prospect, especially when you
need to check the website, conversion path and outreach angle rather than just export a directory.

LeadGap automates that first-pass research and returns the prospects that clear its commercial filters.

---

## What you get for every qualified lead

| Field | Example |
|---|---|
| `businessName` | Bright Smile Dental |
| `city` / `country` | Manchester / UK |
| `website` | https://brightsmilemanchester.co.uk |
| `websiteSource` | `GOOGLE_MAPS` |
| `phone` | +44 161 555 0132 |
| `emails` | ["hello@brightsmile..."] |
| `rating` / `reviews` | 4.8 / 214 |
| `salesPriority` | **HIGH** |
| `confidenceScore` | 90 |
| `opportunityScore` | 62 |
| `primaryOpportunity` | Booking conversion |
| `estimatedDealType` | Booking funnel |
| `recommendedService` | Online booking funnel implementation |
| `revenueImpact` | HIGH |
| `whyThisLead` | "Bright Smile Dental has an active public website, but the automated audit found a specific booking conversion opportunity after checking 4 page(s)…" |
| `pitchHook` | "I reviewed brightsmilemanchester.co.uk and noticed a potential conversion gap: no clear online booking path detected across 4 scanned pages…" |
| `qualificationReason` | "The business has an active website, but no clear online booking path was detected. For an appointment-based business this creates a concrete conversion opportunity." |

Download as **JSON, CSV, Excel**, or pull through the Apify API.

---

## Why LeadGap beats a plain Google Maps scraper

| Plain scraper | LeadGap AI |
|---|---|
| Gives you a business name and phone | Gives you **a reason to call** and **what to sell** |
| Same generic list for everyone | Ranked by **commercial value**, not alphabetical order |
| "No website" = guesswork | Confirmed through **external search + audit** |
| No context for outreach | Ready-to-send **pitchHook** per lead |
| Ignores niche | **Niche-aware rules** (a plumber ≠ a dentist) |

---

## What "qualified" actually means

Every business in your dataset has cleared **four filters**:

1. **Niche relevance** — verified against Google Maps category and business
   name so a "Plumber" search does not return Screwfix.
2. **Real audit** — homepage plus up to 3 internal pages (Contact, Book,
   Appointment) fetched and analysed.
3. **Commercial signal** — online booking, contact/quote form, CTA,
   click-to-call, mobile viewport, analytics, Meta Pixel, live chat.
4. **Sales qualification** — `salesPriority` HIGH/MEDIUM, confidence above
   threshold, `doNotPitch = false`, and a concrete deal type.

Businesses that fail any filter are **silently dropped** — you are not
charged for them and they never pollute your dataset.

---

## Niche-aware logic (this is the hard part)

A plumber does not need online appointment booking. A dentist absolutely does.

LeadGap applies different conversion rules per niche:

- **Home services** (plumber, electrician, roofer, HVAC, cleaner, landscaper,
  locksmith, pest control, handyman) → evaluated on **quote form, contact
  path and click-to-call**, never on booking.
- **Appointment businesses** (dentist, orthodontist, med spa, beauty salon,
  hair salon, nail salon, lawyer, solicitor, accountant) → evaluated on
  **online booking path**, which is the highest-converting opportunity for
  these niches.
- **Food & hospitality** (restaurant) → niche relevance is supported, while
  commercial scoring currently uses the general website/conversion audit.
  Dedicated menu/reservation scoring is not yet claimed by this release.

This is why LeadGap costs more than a scraper — the niche logic took longer
to build than the scraping.

---

## Website source values

- `GOOGLE_MAPS` — the listing supplied the website.
- `EXTERNAL_SEARCH` — LeadGap found a strong website match outside the
  listing and audited it.
- `NOT_FOUND` — no website linked in Maps, and the additional external search
  did not find a sufficiently strong official-site match.

`NOT_FOUND` is **not proof** that the business has no website. LeadGap treats
it as a strong prospecting signal that deserves a final manual check before
outreach.

---

## How to run it (3 steps)

1. Pick a **country**.
2. Enter a **city** and a **business type** — e.g. `Dentist`, `Plumber`,
   `Beauty Salon`, `Lawyer`.
3. Set how many businesses to discover and how many qualified leads you want.

**Example input**

```json
{
  "businessType": "Dentist",
  "city": "Manchester",
  "country": "UK",
  "maxBusinesses": 40,
  "maxResults": 20,
  "minOpportunityScore": 0,
  "websites": []
}
```

Run the Actor → open the **Sales-ready leads** view → export or stream
through the API.

---

## Manual audit mode

Already have a prospect list? Put URLs into the optional `websites` input and
LeadGap will audit exactly those sites — no discovery, no niche filtering.

---

## Pricing

**$0.03 per qualified opportunity** (launch price), plus Apify platform usage.

- You are charged **only** when a qualified lead is written to the dataset.
- Businesses discovered but rejected by the commercial filter are **free**.
- `maxBusinesses` is how many businesses we look at.
- `maxResults` is the maximum number of qualified opportunities returned.
- A run can legitimately return fewer leads than you asked for — that is the
  filter doing its job.

At the launch price, 20 qualified opportunities correspond to $0.60 in LeadGap
qualified-opportunity fees, before any separate Apify platform usage.

---

## Use cases

- **Web agencies** — find local businesses that need a website rebuild,
  booking funnel or lead capture form.
- **Local SEO teams** — prospect businesses with no analytics, no Meta Pixel
  and weak conversion paths.
- **Freelancers** — build a 30-lead pipeline in the time it takes to drink
  one coffee.
- **AI agents & automations** — feed structured, ranked leads into your own
  outreach workflow via the Apify API, n8n, Make or Zapier.

---

## Integrations

LeadGap runs on Apify, so it plugs into:

- **Apify API** — pull structured leads into any app.
- **n8n / Make / Zapier** — schedule runs, push leads into your CRM.
- **AI agents** — the output is designed to be consumed by an LLM: each
  record already contains `whyThisLead`, `recommendedService` and
  `pitchHook`, so your agent does not have to invent them.

---

## Accuracy and responsible outreach

LeadGap audits publicly available business and website information.
Websites, contact details and local categories change, and automated
classification is never perfect. Review high-value prospects before
contacting them — especially `NOT_FOUND` website cases and ambiguous local
categories.

Use the data in accordance with applicable privacy, marketing and anti-spam
rules in your jurisdiction.

---

## Feedback

Found a niche you want covered? Missing a signal that matters for your
outreach? Message us through the Actor page — new niche rules ship weekly.
