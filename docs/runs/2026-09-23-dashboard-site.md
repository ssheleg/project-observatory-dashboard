# Dashboard website and repository rename — 2026-09-23

## Objective and bounded plan

Rename the existing public repository, put the agent installation prompt on the
first screen, improve the marketing UI, verify compatibility/privacy, then deploy.
Owner: `ssheleg/project-observatory-dashboard`, branch `codex/observatory-dashboard-site`.
Starting revision: `0ffdc4bcafaacdba0d9c846034c6eaf582869354`.

Requirements: R1 repository identity; R2 prompt-first installation; R3 responsive
product illustration; R4 unchanged runtime/schema compatibility; R5 verified
production delivery. Scenarios and visual rubric: [site brief](../site/BRIEF.md).
Shared contracts: [migration](../MIGRATION.md), [agent onboarding](../AGENT-ONBOARDING.md),
[static deployment](../site/DEPLOY.md). No second repository or private dashboard
copy is created. GitHub name only; the existing local checkout folder can keep its
historical name. Historical receipts and released schema IDs retain old addresses.

## Implemented

- Renamed the same public GitHub repository; v0.1.0/v0.2.0 releases remain present.
- New home composition with prompt copy, native disclosure and fictional preview.
- Clipboard rejection reveals/selects the full prompt; pending button state clears.
- Active source/install/article URLs use the new slug. Command, state format and
  immutable Fabric identifiers remain unchanged. No package release required.
- Public pages retain canonical URLs and static content, with content-hashed assets.

## Verification and delivery

Local checks passed: static allowlist with 9 negative probes; article source/render
parity; exact clipboard payload, pending/retry and denied/unavailable clipboard
recovery tests; public tree/history privacy gate (315 files, 434 blobs, no findings;
pattern-based check, no private denylist supplied). Brand lint: 0 errors, 360 advisory
warnings across the inherited pack. New marketing copy received an editorial pass
for concrete claims and repeated wording; no new statistics or testimonials.

CUA browser review: populated home at 1280×900, 390×844 and 320×740; no horizontal
document overflow, copy control in first viewport. Prompt disclosure and example
toggle worked. Article at 320px also fits; no browser warnings/errors observed.
Clipboard success status observed; CUA's clipboard reader returned empty, so exact
payload is verified by the offline interaction test, not claimed as a browser read.
No screen-reader or complete WCAG audit claimed. Forest and paper renders compared;
paper selected under the site's recorded rubric. Repository redirect and pinned
v0.2.0 schema response checked over HTTP. Production receipt follows below.

## Local-only boundary

Do not commit or deploy any keys, private workspace, generated dashboard, actual
project registry, caches or machine configuration. Only the thirteen allowlisted
site files are deployment inputs. CI uses synthetic state. Private original project
is separate and untouched. Never create another repository at the old slug while
published schema identifiers still depend on GitHub's rename redirect.

## Next task

After this delivery, monitor user feedback about setup completion. No runtime UI
redesign, provider expansion or schema migration is implied by this website change.


Initial CI identified the provider-header URL edit as an inventory digest change.
Updated that file's exported digest and byte count in SOURCE-INVENTORY.json;
original source provenance stays unchanged. The package gate remains enforced.
Humanization: on — humanizer plus editorial review of new landing copy; retained
concrete mechanism and limits, no further wording changes after review (0%).

The new offline CommonJS test also required an explicit path in the public-source
allowlist. Only `tools/check_site_interactions.cjs` is admitted; arbitrary `.cjs`
files remain refused and the admitted file still receives content/privacy scans.
A regression test verifies both boundaries. No privacy rule was disabled.


## Completed delivery

- Public owner: [ssheleg/project-observatory-dashboard](https://github.com/ssheleg/project-observatory-dashboard).
- Implementation: [96c8556](https://github.com/ssheleg/project-observatory-dashboard/commit/96c85560800edbf582aa75020ca024ccadb4fd1c),
  merged through [PR 10](https://github.com/ssheleg/project-observatory-dashboard/pull/10).
  Its tree equals tested head `3ccd405fc745a9370ef4249e997b0ae364d19f21`.
- [PR CI](https://github.com/ssheleg/project-observatory-dashboard/actions/runs/35846791547)
  and push CI passed on Linux Python 3.11/3.14 and macOS Python 3.14. Each includes
  33 full-engine offline suites, wheel inspection, public source/history checks,
  site gates and sterile installation. The new focused publication-boundary suite
  passes 11 tests locally.
- Fresh HTTPS clone of the renamed repository resolves to the tested head. Its
  static self-tests, article parity and offline site interactions pass independently.
- Cloudflare production deployment `be77ca89-cd8d-4f48-b9c9-31ec0365613a`, source
  `96c85560800edbf582aa75020ca024ccadb4fd1c`.
  [Deployment receipt](../site/evidence/2026-09-23-dashboard-deployment.json).
- [Live website](https://observatory.sshlg.me/): all 12 served files match the
  committed source byte-for-byte. The thirteenth input is the response-header
  policy. CSP, nosniff and referrer headers are present; an unknown URL returns
  HTTP 404 with the reviewed recovery page.
  [HTTP/hash receipt](../site/evidence/2026-09-23-dashboard-production.json).
- Production browser: home at 1280×900, 390×844 and 320×740; document fits viewport.
  At 320px with scrollY=0, the copy button ends at 593.65px. Copy success status,
  prompt disclosure, article navigation and 404 recovery verified. Exact clipboard
  payload remains covered by the offline test; see browser-reader limitation above.
- Released Fabric schemas/fixtures: `python3 observatory/engine/tools/publish_contract.py --check`
  returns `publication_identical: true`; external host admission remains unverified.
- Repository description, homepage and topics now describe the dashboard. No new
  repository, release, domain, integration or private workspace was created.

Capture record: production `/`, populated illustrative state, English, paper Field
Notes theme, no animated content, system font loaded; source is CUA in-app browser;
revision is the deployment source above. Captured 2026-09-23. Both desktop and mobile
screens were visually inspected. This is browser evidence, not native-device or
complete accessibility certification. No production conversion result is asserted.

All requested work in this bounded task is complete. The next optional work remains
collecting setup feedback; there is no required migration step for existing users.

## Skills actually used

- ux-scenarios: recorded SITE-12 through SITE-14 and linked runtime boundaries.
- sheleg-design: retained Field Notes tokens; compared forest and paper; reviewed
  responsive renders. No new visual assets or external font dependencies.
- copywriting: public landing and setup wording against the existing brand pack.
- humanizer (outside the family): reviewed new copy for inflated and stock wording.
- task-pipeline: bounded requirements, CI fixes, integration, receipts and handoff.
- cloudflare (outside the family): scoped deployment of reviewed static files.

**Made with [ssheleg skills](https://github.com/ssheleg/sshlg-skills)**
