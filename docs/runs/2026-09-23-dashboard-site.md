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
v0.2.0 schema response checked over HTTP. Production receipt pending below.

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
