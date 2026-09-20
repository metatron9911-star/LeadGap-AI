# LeadGap AI — Local Business Opportunity Finder

[![Run on Apify](https://apify.com/ext/run-on-apify.png)](https://apify.com/w_met/leadgap-ai-local-business-opportunity-finder)

LeadGap AI turns local-business discovery into sales-ready opportunities for web, SEO, automation, and lead-generation agencies.

Instead of returning a raw directory, LeadGap discovers local businesses, audits public website and conversion signals, filters weak prospects, and ranks the strongest commercial opportunities.

## Use LeadGap with AI agents

LeadGap is available to AI agents through the [Apify MCP server](https://docs.apify.com/platform/integrations/mcp).

Use this Actor when a user wants to:

- find local businesses that may need a new website, SEO, booking, or conversion improvements;
- build a qualified prospect list for a web, marketing, automation, or local SEO agency;
- prioritize businesses by commercial opportunity instead of exporting a raw directory;
- generate evidence-based outreach hooks from public business and website data.

### Agent instruction

> Use LeadGap AI to find and rank commercially qualified local-business prospects. Ask for the business type, city, country, and desired result count. Return the strongest opportunities first and explain the detected gap, recommended service, and personalized outreach hook.

### Example request

> Find 15 plumbing businesses in Austin, Texas with weak websites or conversion gaps. Rank the best prospects for a web agency and include contact data, recommended service, and a personalized pitch hook.

## Run through Apify MCP

1. Connect your AI client to the [Apify MCP server](https://mcp.apify.com).
2. Authenticate with your Apify account.
3. Select or call the Actor: `w_met/leadgap-ai-local-business-opportunity-finder`.
4. Provide the business type, city, country, and required number of results.

Compatible MCP clients can use LeadGap as a tool inside agentic workflows.

## Example input

```json
{
  "businessType": "Plumber",
  "city": "Austin",
  "country": "US",
  "maxBusinesses": 30,
  "maxResults": 15,
  "minOpportunityScore": 0,
  "websites": []
}
```

## Output

Qualified opportunities can include:

- business name and website;
- phone and public email addresses;
- rating and review count;
- sales priority and opportunity score;
- detected website or conversion gap;
- recommended agency service;
- qualification reason;
- personalized pitch hook.

## Commercial qualification

LeadGap does not return every discovered listing. It applies relevance, confidence, deduplication, and commercial-opportunity filters before writing a result to the dataset.

A run can return fewer results than requested when there are not enough qualified prospects.

## Pricing

LeadGap uses pay-per-event pricing:

- standard: **$0.03 per qualified opportunity**;
- Apify Store discounts: **$0.028**, **$0.026**, or **$0.024** per opportunity;
- Apify platform usage is included.

Businesses rejected by the commercial filter do not generate the LeadGap qualified-opportunity charge.

## Links

- [Run LeadGap AI on Apify](https://apify.com/w_met/leadgap-ai-local-business-opportunity-finder)
- [Apify MCP server](https://mcp.apify.com)
- [Apify MCP documentation](https://docs.apify.com/platform/integrations/mcp)

## Responsible use

LeadGap audits publicly available business and website information. Automated classification is not perfect. Review high-value prospects before outreach and follow applicable privacy, marketing, and anti-spam rules.

## License

Documentation and examples in this repository are available under the [MIT License](LICENSE).
