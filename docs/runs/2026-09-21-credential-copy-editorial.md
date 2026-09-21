# Credential-copy editorial revision

## Brief and route

Operator request: rewrite the canonical field-notes article and Telegram RU/EN,
X and LinkedIn EN posts around unnoticed API-key copies during Claude Code work.
The article should earn attention through a personally relevant risk. Existing
standing authorization covers repository delivery and website deployment; social
account publication is outside this task. No intake question was needed.

Read: docs/brand/{voice,terminology,facts,channels}.md, locale records,
docs/site/{BRIEF,CASE-STUDY}.md, docs/content/long-post.md at baseline
4667ecba646a20c7bbafb4b8a43d8e6b16b5dc65; official Claude Code hook reference and
claude-mem lifecycle documentation, checked 2026-09-21.

Contradiction resolved: the request's "leaked" framing can mean external theft;
our evidence establishes retained local copies. Copy leads with the risk and
preserves this distinction. Claude Code and optional third-party memory are distinct.

Route read from copywriting and brand-voice SKILL.md in the installed Agent Skills
catalog; task-pipeline SKILL.md from the installed 1.87.0 plugin. Existing visual
layout and component behavior are unchanged; this is an editorial change.

## Requirements and checks

- Article: clear Claude Code/API-key hook, illustrative copy path, historical
  aggregate with correct units, limits beside evidence, practical next action.
- Channels: Telegram EN/RU, X EN/RU and LinkedIn EN each link to the canonical
  article. Short article and X Article remain aligned. Socials stay drafts.
- SEO: page title, description, Open Graph, Article schema and landing article
  card use the updated story; canonical address remains stable.
- Delivery: brand lint, static allowlist/negative probes, Markdown/HTML text parity,
  privacy check, remote CI, browser desktop/mobile and verified production deploy.

## Implementation and editorial judgement

New article: 845 whitespace-delimited words. Two headline alternatives considered:
"Is your API key still in your Claude Code history?" is shorter but names no
retention mechanism; "The API keys your agent leaves behind" is punchier but
asserts copying too broadly. Selected headline keeps possibility explicit and
names the artifact: "Claude Code finished. Your API key may still be in the logs".

Seven sweeps: simplified the opening, retained the peer-builder voice, connected
persistence to transcript sharing, checked claims against evidence, kept event
units exact, used a concrete risk, and offered local inspection without asking
for secrets in chat. Humanization: on, own pass for each surface. One unnecessary
explanatory sentence was removed; Russian modality and evidence location were
made precise. [Per-surface measured edit rates](2026-09-21-editorial-review.json)
compare the newly written draft to the reviewed result, not the deliberately
replaced old article. No unmeasured marker count or authorship claim is reported.

Brand-voice updated sourced facts and the shorter Telegram adaptation policy;
copywriting wrote the eight assets; task-pipeline carries verification and Git
handoff. Existing Cloudflare deployment procedure is reused. No new design or
runtime behavior was introduced.

## Checks observed before integration

`python3 docs/site/check.py --self-test`: 11 static files, eight negative probes PASS.
`python3 docs/brand/lint.py --brief`: 0 errors / 310 inherited whole-engine warnings.
These warnings include unregistered legacy strings; no complete copy-coverage claim.

Article Markdown/HTML text parity and all five social links PASS; X EN/RU fit
the chosen short-post budget. Browser: article at 390px and 1440px, no overflow;
cover loads; no console warnings/errors. New headline appears in rendered HTML.

## Handoff and local-only rule

Source of editorial truth: docs/content/long-post.md; rendered article:
site/field-notes/index.html. Brand facts and case-study scope constrain all channel
adaptations. Do not include real keys, project identities, raw logs or private
receipts. A new security case needs evidence review before any public claim.

## Production delivery

Complete. Source [ba96b75](https://github.com/ssheleg/project-observatory-open-source/commit/ba96b7587ed1f0d85130547f68897228340f1e85)
merged via PR4 after all supported jobs passed in
[CI](https://github.com/ssheleg/project-observatory-open-source/actions/runs/35604193868).
Cloudflare deployment `a21edd50-d8f9-4e38-9298-c67d4299b441` serves that exact source.
All ten public asset bodies match source bytes; response headers match the static
policy. The canonical article was opened in a browser after deployment: new title,
loaded cover, no mobile overflow or console warnings/errors.
[Machine receipt](2026-09-21-editorial-production.json).

The public-tree/history check before the source commit inspected 299 files and
368 historical blobs against 302 private identifiers with zero findings. CI also
rechecks the public history. No new raw incident evidence was accessed or published.

Next task: the operator can copy the reviewed posts from docs/content. No social
account message was sent. Runtime, package version and private services are unchanged.
This documentation-only receipt does not require another site deployment.
