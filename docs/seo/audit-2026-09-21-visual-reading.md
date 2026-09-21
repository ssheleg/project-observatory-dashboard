# Observatory: visual reading and search audit

Scope: home, field notes, static assets and unknown-path handling. Source baseline:
[9707535](https://github.com/ssheleg/project-observatory-open-source/tree/9707535ff7b6a1385b4b906bfe78d4c3ad014e97).
[Plan](plan-2026-09-21-visual-reading.md) → implementation → checks → deployment receipt.

| Evidence | Before | Implemented |
|---|---|---|
| CONFIRMED HTTP | unknown path returned 200/home | explicit noindex 404 recovery document; production status must be checked |
| CONFIRMED article source | prose and cover | measured chart, two diagrams, generated cartoon, two author pull quotes |
| CONFIRMED previews | incomplete image alt/Twitter metadata | explicit image metadata and large-image preview permission |
| CONFIRMED entities | basic product/article nodes | shared WebSite, Person, WebPage and article breadcrumbs |
| CONFIRMED reader structure | long uninterrupted prose | deck, byline, 7-minute estimate, native section contents, readable serif measure |
| CONFIRMED answers | product description | four direct answers covering purpose, private data, scan limits and Skills relationship |

## Evidence and interpretation

[Case-study JSON](../site/case-study.json) remains the chart's source: 66 + 136 = 202
replacement events. Shared linear scale 0–150, visible labels and caption prevent
presenting these as unique stolen credentials. [Illustrations](../content/ILLUSTRATIONS.md)
separates original generated artwork from measured evidence. Diagram paths illustrate
mechanisms; they do not reconstruct a private incident. Quotes are excerpts of the
authorized first-person narrative. No invented third-party endorsements.

Humanizer/editorial pass removed repeated cautions and stock transitions, kept
specific actions and author history, and retained causal limits next to claims.
The optional claude-mem integration remains distinct from Claude Code; the cited
Check Point issues are explicitly described as patched before publication.

Local article review: 1440px and 390/320px, readable first screen, vertical mobile
diagrams, no horizontal overflow. Native contents opens by keyboard and section
links navigate. Four figures exist in static HTML; prose does not depend on JS.
Eight editorial foreground/background pairs exceed 4.5:1, recorded in
[contrast receipt](evidence/contrast.json). This is not a full WCAG certification.

Checks: static gate passes 13 files and 9 negative probes; Markdown renderer check
and repeat-build digest agree; brand lint reports 0 errors (existing engine warnings
remain); source/history privacy scanner finds no private matches. The
[cross-site contract receipt](evidence/local-contract-check.json) records all 16
indexable pages with canonical, heading, JSON-LD, social metadata and anchor checks.

Search Console reports both Observatory URLs unknown/not yet crawled. The unspecified
fetch state is not evidence of an HTTP fetch failure. Sitemap is advertised in robots;
it was absent from the property sitemap list during baseline inspection. Direct
answers are useful without FAQ schema; the tool's low-priority missing-FAQ-schema
suggestion was not adopted as a ranking requirement. Remaining indexing and
performance outcomes require later external data, not copy padding.

## Method and limits

Measured on 2026-09-21. HTTP/HTML evidence covers all 16 indexable URLs across the
two sitemaps; source checks cover their generated/static counterparts. CONFIRMED
means observable markup/status, FIELD means a tool heuristic, and UNMEASURED
means no outcome evidence. No ranking, indexing or AI-citation improvement is claimed.

Google's [Article documentation](https://developers.google.com/search/docs/appearance/structured-data/article)
supports accurate article entities; [AI features guidance](https://developers.google.com/search/docs/appearance/ai-features)
requires no special AI schema; [Discover guidance](https://developers.google.com/search/docs/appearance/google-discover)
explains large-image permission without promising inclusion. These are primary
references, checked during this revision.

Coverage: crawling/indexability, canonicals/sitemaps, titles/descriptions, headings,
static answer text, author/entity/structured-data relationships, social previews,
internal links, rendering and scoped accessibility. Full external backlink analysis,
conversion analytics and API/MCP distribution are outside this website change.
PageSpeed Insights returned HTTP 429: no new lab performance or field Core Web Vitals
result is claimed. Search Console inspection is a dated observation, not a crawl
request or forecast. Raw account responses, traffic analytics, credential material
and local configuration stay outside Git.

## Production closure

[Production receipt](evidence/production-2026-09-21.json) confirms source commit
[0dca204](https://github.com/ssheleg/project-observatory-open-source/commit/0dca20438372c0359786327f2ddf98747dc44845),
12 matching served files, response security headers and an unknown route returning
404 with the reviewed recovery document. Cloudflare deployment:
`69a58836-27a3-4ab5-b841-e18130b5b9a9`. The rendered article has four figures and two
pull quotes. Its browser console has no warnings/errors in the reviewed flow.

After publication, the existing public sitemap was registered through the owner's
existing Search Console access (HTTP 204), then read back successfully. Processing
is pending, with zero reported errors/warnings at submission. This does not establish
indexing. No OAuth scopes or account permissions were changed.
