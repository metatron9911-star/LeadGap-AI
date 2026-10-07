# LeadGap AI — Local Leads, Website Gaps & Outreach Angles

**Find local businesses with real website gaps, public contact details, and a grounded reason to contact them.**

LeadGap AI is built for agencies, freelancers, consultants, and outbound teams that do not want another raw Google Maps export. It discovers or audits local businesses, checks their web presence, separates stronger opportunities from lower-confidence candidates, and returns evidence-based outreach angles you can actually use.

## What you get

A qualified LeadGap result can include:

- business name, niche, city, and country
- website and website-source confidence
- public phone, email, and social links when available
- opportunity score and confidence score
- the primary website or conversion gap detected
- recommended service to pitch
- sales priority
- a plain-English reason why the business qualified
- a grounded outreach hook tied to the detected issue

**LeadGap does not verify email deliverability.** Contact data is filtered from publicly available sources and should still be reviewed before outreach.

## Popular use cases

### Find dentist leads in London
Discover dental practices with visible appointment, contact, mobile-conversion, or website gaps and rank the strongest outreach opportunities.

### Find plumber leads
Find local plumbing businesses whose web presence suggests a realistic redesign, lead-capture, mobile-contact, or local SEO opportunity.

### Find restaurants with weak websites
Audit restaurant websites for reservation, ordering, mobile contact, and conversion-path friction.

### Find med spa, beauty salon, lawyer, and accountant leads
Use niche + city discovery to build targeted local prospect lists instead of buying generic lead databases.

### Audit your own prospect list
Skip discovery and submit website URLs directly when you already have a list of businesses you want LeadGap to evaluate.

## Best for

- web design and development agencies
- local SEO agencies
- automation agencies
- freelancers and consultants
- lead-generation teams
- appointment-setting and outbound-sales workflows

## How it works

1. Choose a country, city, and business niche.
2. LeadGap discovers local businesses or audits URLs you supply.
3. It checks the business website and public contact footprint.
4. It scores the commercial opportunity and confidence.
5. Stronger opportunities are written to the sales-ready dataset.
6. Lower-confidence candidates remain clearly separated for manual review.

## Input

Typical discovery input:

```json
{
  "country": "UK",
  "city": "Manchester",
  "businessType": "Dentist",
  "maxBusinesses": 30,
  "maxResults": 10,
  "minOpportunityScore": 0,
  "websites": []
}
```

You can also use **Manual website audit** to skip discovery and inspect a supplied list of public URLs.

## Output example

```json
{
  "businessName": "Example Dental Practice",
  "businessType": "Dentist",
  "city": "Manchester",
  "salesPriority": "HIGH",
  "opportunityScore": 72,
  "confidenceScore": 94,
  "primaryOpportunity": "Appointment conversion",
  "recommendedService": "Booking and mobile conversion optimization",
  "website": "https://example.com",
  "phone": "+44...",
  "emails": ["info@example.com"],
  "whyThisLead": "The site has a visible conversion gap in the appointment journey.",
  "pitchHook": "I reviewed your mobile appointment path and found a point where high-intent visitors can drop before booking."
}
```

## Ready for outreach vs manual review

LeadGap is designed to avoid pretending every scraped business is equally valuable.

**Sales-ready leads** are the candidates that pass the current opportunity and confidence checks.

**Needs manual review** is for candidates where the evidence is weaker or the website/business match needs human confirmation.

## Pricing

LeadGap uses pay-per-event pricing for qualified opportunities.

- standard price: **$0.03 per qualified opportunity**
- volume tiers can reduce the per-opportunity price

You pay for qualified opportunities delivered to the dataset, not for every business inspected during discovery.

## 60-second demo flow

**Manchester + Dentist → inspect 30 businesses → return up to 10 qualified opportunities → review website gap, public contacts, priority, and outreach hook.**

The public Example Tasks in the Apify Store let you launch common scenarios without configuring the Actor from scratch.

## API, automations, and AI agents

LeadGap can be run from the Apify Console, API, scheduled Tasks, integrations, and Apify MCP workflows. The public Example Tasks are intentionally named around concrete buyer jobs so they can be discovered by people and AI agents looking for local lead-generation and website-gap workflows.

Common automation pattern: **niche + city → qualified opportunities → export/API → CRM or outreach review**.

## Notes


- Results depend on the availability and quality of public business and website data.
- Public contact details are filtered, but email deliverability is not verified.
- A missing or uncertain signal is not silently treated as a confirmed sales fact.
- Use outreach responsibly and follow applicable privacy, anti-spam, and local marketing rules.

## Current positioning

LeadGap AI is not a generic business-list scraper. It is a **local-business opportunity finder** for teams that need a reason to contact a prospect, not just a row in a spreadsheet.
