# LeadGap AI — Local Business Website Gap Finder

![LeadGap AI — Find the gap. Start the conversation.](https://raw.githubusercontent.com/metatron9911-star/LeadGap-AI/leadgap-sellable-v1/docs/assets/LeadGap_Hero.jpg)

Find local businesses with actionable website gaps, public contact details, and grounded outreach angles.

LeadGap helps web design, local SEO, lead-generation agencies and freelancers decide **who to approach and what to discuss**. Choose a niche and city, run the audit, then review the opportunities.

## What you get

- Local business discovery and website checks.
- Opportunity and confidence scores, sales priority and a recommended service.
- A reason for qualification and an outreach hook tied to what the audit detected.
- Public phone numbers, emails and social links when available.
- Qualified opportunities and **Needs manual review** kept separate.

## Quick start

1. Select the country, city and business type.
2. Set how many businesses to consider and the maximum qualified results.
3. Run the Actor.
4. Open **Sales-ready leads** to review qualified opportunities.
5. Export JSON, CSV or Excel. Check the business and contact route before outreach.

### Dentist / London

```json
{
  "country": "UK",
  "city": "London",
  "businessType": "Dentist",
  "maxBusinesses": 30,
  "maxResults": 10,
  "minOpportunityScore": 0,
  "websites": []
}
```

For restaurants, use `"businessType": "Restaurant"` and `"city": "Manchester"`. Restaurant opportunities focus on reservation, ordering and contact journeys; dental opportunities focus on appointment and enquiry journeys.

`maxBusinesses` is the number considered. `maxResults` is a cap on qualified output, not a promise that every listing will qualify. A run can return fewer results, including zero.

### Audit a known list

Add URLs to `websites` to audit them directly instead of discovering businesses. Use the relevant business type to give the audit niche context.

## What is a qualified opportunity?

A business that passes LeadGap's relevance and commercial filters, meets its confidence threshold, has HIGH or MEDIUM sales priority and an actionable service angle, and is written to the qualified dataset.

Qualification means **a prospect worth checking**, not a confirmed buyer or a guaranteed sale. An automated check that did not detect a booking or contact feature does not prove it is absent everywhere. Dynamic widgets, unscanned pages and third-party services can require a manual check.

### Real output excerpt

The following excerpt comes from a Restaurant / Manchester run. Results change as websites and listings change.

```json
{
  "businessName": "Toro's Steakhouse Manchester",
  "businessType": "Restaurant",
  "city": "Manchester",
  "country": "UK",
  "website": "https://torosuk.com/",
  "websiteSource": "GOOGLE_MAPS",
  "phone": "+44 161 795 5447",
  "emails": [],
  "salesPriority": "MEDIUM",
  "opportunityScore": 20,
  "confidenceScore": 95,
  "primaryOpportunity": "Mobile lead capture",
  "recommendedService": "Mobile contact conversion optimization",
  "pitchHook": "I reviewed Toro's Steakhouse Manchester and could not confirm a click-to-call path for mobile visitors. The audit evidence was: No click-to-call telephone link detected. For a restaurant, I would test that contact path first because it affects diners who want to act immediately."
}
```

The full record can also contain rating, reviews, address, social links, opening hours, qualification reason and audit coverage.

## Needs manual review

Some candidates show a promising opportunity but the audit covers only one page and confidence is below the qualification threshold. These records are saved separately under **Storage → Key-value store → NEEDS_REVIEW**.

They include `reviewStatus: "NEEDS_REVIEW"` and a `reviewReason`. Inspect the site and business match before using them for outreach. They are **not written to the qualified dataset and do not trigger the Qualified opportunity charge**. An empty review list is a valid result.

## Contact data and email hygiene

LeadGap extracts publicly available contact information and applies filters for placeholder addresses, unrelated domains and some location mismatches. Email can be empty; the business may still have a public phone or another contact route.

This is contact discovery and filtering, **not mailbox or deliverability verification**. Check the relevant branch and validate an address before emailing. No email address is invented when none is available.

## Website source

- `GOOGLE_MAPS`: supplied by the business listing.
- `EXTERNAL_SEARCH`: found through an additional website search.
- `NOT_FOUND`: no sufficiently strong official-site match was found.

`NOT_FOUND` is a prospecting signal, not proof that the business has no website. Confirm the match manually.

## Pricing

**$30 per 1,000 qualified opportunities ($0.03 each)** at the standard rate.

Apify plan discounts: Bronze $28, Silver $26, Gold $24 per 1,000. This is why the Store may show “from $24”.

The billable event is **Qualified opportunity**. It is associated with accepted qualified dataset output. Discovered listings, rejected candidates and Needs manual review records do not trigger that event. Under the current Actor pricing settings, users do not pay separate Apify platform usage costs for this Actor.

## Trial

Want to see the output before choosing your workflow? Email **leadgapaicatalogfix@gmail.com** with your niche, city and country.

**We will run LeadGap on 10 local businesses and send the qualified opportunities found, with review candidates clearly labelled.** Ten businesses inspected does not guarantee ten qualified leads.

## Integrations

Use the Apify API, scheduling, or Apify MCP to connect LeadGap to your workflow. Export qualified records to your CRM or spreadsheet after review.
