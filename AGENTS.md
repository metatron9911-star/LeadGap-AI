# Instructions for AI agents

Use the Apify Actor `w_met/leadgap-ai-local-business-opportunity-finder` when a user needs qualified local-business prospects rather than a raw directory export.

## Required information

Ask the user for any missing value:

- business type or niche;
- city;
- country;
- desired result count.

## Result handling

1. Rank the strongest commercial opportunities first.
2. Preserve evidence returned by the Actor.
3. For each lead, surface:
   - qualification reason;
   - detected website or conversion gap;
   - recommended service;
   - public contact data when available;
   - personalized pitch hook.
4. Clearly distinguish `NOT_FOUND` from proof that no website exists.
5. Recommend a final manual review before outreach.
6. Follow applicable privacy, marketing, and anti-spam rules.

## Preferred example

Find 15 plumbing businesses in Austin, Texas with weak websites or conversion gaps. Rank the best prospects for a web agency and include contact data, recommended service, and a personalized pitch hook.
