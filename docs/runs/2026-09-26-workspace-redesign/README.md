<sub>ssheleg skills — ux-flows · ux-scenarios · ux-audit · sheleg-design · copywriting · accessibility-review · task-pipeline · evidence-docs</sub>

# Dashboard workspace redesign delivery

Objective: make every primary inventory immediately readable, review all ten
dashboard screens and preserve their operational capabilities. Start with the
[design and acceptance brief](../../ux/DASHBOARD-REDESIGN.md) and
[audit receipt](../../ux/audits/2026-09-26-workspace-redesign.md). This repository
owns the implementation; generated private pages and browser captures stay local.

Baseline:
[`327d656f`](https://github.com/ssheleg/project-observatory-dashboard/commit/327d656f).
The brief was recorded in
[`abbd3df`](https://github.com/ssheleg/project-observatory-dashboard/commit/abbd3df).
The final implementation commit, remote branch verification and fresh-checkout
receipt are **pending** and must be filled from actual results before handoff.

## Completed implementation

- Grouped navigation rail, visible main landmark and skip link; concise headings;
  compact mobile navigation with all ten routes.
- Visible inventory defaults, compact project comparison rows, full linked
  project detail, global sorting and narrow-screen sort control.
- Honest bounded attention preview, visible matching findings and independently
  accessible acknowledged history; disclosure reserved for secondary detail.
- Health begins with observer state, snapshot context and recovery; Keys/ENV
  state whether actions copy commands or execute; hosting and traffic summaries
  appear beside the records they describe.
- GA4 resources normalized by declared resource identity across credentials;
  conflicting/unknown metrics and partial coverage retained without invented zero
  or unique-person claims.

The [audit](../../ux/audits/2026-09-26-workspace-redesign.md) maps each statement to
source functions, synthetic checks and browser observations. The full-engine
contract is [OSS-13–18](../../../observatory/engine/docs/ux/portable-scenarios.md).
Public site and compatibility CLI redesign are outside this change.

## Delivery status and next task

| Stage | Recorded status |
|---|---|
| Implementation and ten-screen audit | Complete for this change; evidence linked above |
| Focused regression checks | 58 portable suites PASS across final run + six timeout retries; final footer 8 cases PASS; package 60 cases PASS |
| Browser | Safari ten-route first pass; Chromium desktop/narrow Projects, detail/Escape, search and sort second pass; limits in audit |
| Full repository gate | All local test phases PASS; original 120 s full-run timeouts preserved in validation.json |
| Privacy, inventory and package gates | Source inventory PASS; wheel inspection PASS (278 runtime / 284 archive files); private-identifier scan PASS (382 files, 3776 entries) |
| Final commit, push and fresh checkout | Pending; do not treat this worktree as remote delivery |
| Protected merge / 0.3.12 release | Pending; CHANGELOG/version edits are preparation, not publication |
| Installed update and smoke | Pending; a pushed or merged source change is not an installed update |

**Exact next task:** push the validated implementation and complete protected
integration, release and installation.
The [validation receipt](validation.json) preserves the successful phases and all
timeouts without treating them as passing runs.
Then commit and push only task-owned files, verify the remote commit from a fresh
checkout, follow protected-main integration, publish the reviewed 0.3.12 release,
and update the installation under the existing workspace backup/service policy.
Verify installed version, served page assets, dashboard route, visible Projects
and ENV, Health, and preserved service recovery before declaring delivery complete.

Do not pipeline a gate through a command whose success masks its exit code.
This public repository retains its existing free push/PR CI matrix. The private
estate batch policy is unchanged; missing or billing-blocked CI does not count
as green. Do not publish operational registries, secrets, private paths,
screenshots or generated dashboard HTML. Preserve all unrelated work in progress.

## Shared contracts and task packets

- UI-01–03: shell, workspace CSS and project list/detail; see
  [brief](../../ux/DASHBOARD-REDESIGN.md#requirements-and-acceptance).
- UI-04–07: finding state, action capability, infrastructure/traffic measurement
  and observer snapshot; see [audit dispositions](../../ux/audits/2026-09-26-workspace-redesign.md#findings-and-disposition).
- UI-08: keyboard, narrow screen and theme behavior; see
  [browser scope](../../ux/audits/2026-09-26-workspace-redesign.md#browser-and-accessibility-receipt).
- UI-09: this entry is the final receipt location. Fill final commit, checks,
  remote/fresh-checkout, release and installed status from measured results.

Actual skills: ux-flows and ux-scenarios defined journeys/contracts; ux-audit
reviewed ten screens; sheleg-design supplied composition; copywriting clarified
action wording; accessibility-review checked keyboard/narrow/token contrast
scope; task-pipeline carries integration; evidence-docs records proof and limits.

---

**Made with [ssheleg skills](https://github.com/ssheleg/sshlg-skills)**
