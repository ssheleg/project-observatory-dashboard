<sub>ssheleg skills — ux-flows · ux-scenarios · ux-audit · sheleg-design · copywriting · accessibility-review · task-pipeline · evidence-docs</sub>

# Workspace redesign audit — 2026-09-26

Implementation and browser review are complete for the bounded dashboard change;
local validation is complete; protected integration, release and installed
verification are **pending**. This is a development audit, not a production acceptance receipt.
The [delivery entry](../../runs/2026-09-26-workspace-redesign/README.md) owns the next
steps and outstanding receipts.

## Scope and baseline

The operator rejected tables that conceal project identities until groups are
expanded and requested a review of all dashboard screens. The
[design brief](../DASHBOARD-REDESIGN.md) defines UI-01–09; the full-engine scenario
contract is [OSS-13–18](../../../observatory/engine/docs/ux/portable-scenarios.md).
The compatibility CLI and public marketing site are separate surfaces.

Baseline: commit
[`327d656f`](https://github.com/ssheleg/project-observatory-dashboard/commit/327d656f).
The current implementation retains page filenames, entity hashes, separate page
payloads, offline rendering and protected credential actions. Sources are
[shell.py](../../../observatory/engine/dashboard/shell.py),
[build_dashboard.py](../../../observatory/engine/dashboard/build_dashboard.py) and
[workspace.css](../../../observatory/engine/dashboard/workspace.css).
This report contains no operational inventory, private names or screenshots.

## Findings and disposition

| ID | Baseline defect and receipt | Current change and proof |
|---|---|---|
| R-01 | Group folding hid primary project and ENV rows; baseline `build_dashboard.py:2209–2217,2337–2338,2953–2962` | Projects are a flat comparison table; ENV rows start visible. `test_projects_and_env_show_records_without_expanding_groups` in [workspace tests](../../../observatory/engine/tests/test_workspace_redesign.py); Safari Projects/ENV walkthrough |
| R-02 | Overview treated an empty critical-only slice as no open findings; baseline `shell.py:214–223` and `build_dashboard.py:3415–3419` | Severity totals remain complete; a bounded preview includes warnings, clears inherited folds and links to exact findings. `test_warning_only_preview_is_not_empty_and_preserves_counts`, `test_overflow_is_bounded_visible_ranked_and_does_not_mutate_source` and renderer `test_warning_only_overview_keeps_attention_visible` |
| R-03 | The same early return concealed acknowledged history when no open findings remained; baseline `build_dashboard.py:3416–3419,3471–3477` | Acknowledged reason and undo command remain reachable. `test_acknowledged_only_findings_retain_reason_and_undo` |
| R-04 | The sole main landmark was hidden on Overview, Findings and Health; baseline `build_dashboard.py:1332–1333,1480` | `shell.page_html` creates visible `main#workspace`, skip link and page-specific current navigation. `test_all_pages_have_one_main_containing_their_primary_content` checks every route and Overview DOM order |
| R-05 | Health appeared below unrelated inventory and movement tiles; baseline `build_dashboard.py:1325–1341,1482–1500` | Observer content follows the heading, with snapshot-qualified status, recovery commands and queue. `workspace.css:238–275`, `shell._observer`, `test_the_health_panel_shows_what_the_store_holds`; Safari walkthrough |
| R-06 | Sorting restarted inside groups; narrow layouts hid the table header and its sort buttons; baseline `build_dashboard.py:1362–1364,2243–2265` | Selected records are globally sortable, with a separate narrow-screen control. `test_traffic_is_comparable_across_account_boundaries`; Chromium narrow Projects inspection |
| R-07 | Copy actions used execution verbs without local capability explanation; baseline `build_dashboard.py:3396–3404,3463` | Copy commands are labelled at their buttons; Keys/ENV explain capability before rows. `test_copy_only_credentials_and_refresh_say_command`; existing portability and uncertain-outcome suites remain required |
| R-08 | Traffic presentation treated unknown as zero; duplicate observations could multiply resource totals | Canonical resource identity, retained credential provenance, explicit conflicting/unknown measurements, partial coverage and resource-sum wording. [Google identity tests](../../../observatory/engine/tests/test_google_identity.py), especially `test_same_id_counts_once_and_retains_credential_provenance`, `test_conflicting_successes_are_unknown_and_explicitly_degraded`, `test_zero_is_measured_but_an_error_is_not`; shell `test_traffic_summary_distinguishes_unknown_zero_and_partial_resource_sum` |

Baseline line references above address the named baseline commit. Current proof is
linked by function/test name so the evidence survives line movement in the final
implementation commit; final commit and remote receipt remain pending.

## Screen-by-screen review

| Screen | Result reviewed | Evidence |
|---|---|---|
| Overview | Attention first in visual and DOM order; short preview, labelled boundary, exact finding links; no ambiguous navigation badge | `shell.slice_for`, `shell.page_html`, `renderFindings`; shell tests |
| Projects | Visible compact identity/activity/resource/hosting/audience rows; full project detail and return path | `renderProjects`, `detail`; workspace tests and Chromium detail/Escape walkthrough |
| Findings | Visible titles and matches; secondary evidence/action disclosure; independent acknowledged history | `renderFindings`; warning-only and acknowledged-only renderer tests |
| Domains | Visible identities, reachability and expiry; project/account/evidence destinations retained | `renderDomains`; Safari walkthrough and existing page/render checks |
| Heroku | Seven-column comparison; cost estimate and measurement above rows; resources/paths in secondary detail | `renderHeroku`; Safari walkthrough; focused hosting tests remain part of validation |
| Keys | Visible records and status with copy/live capability stated before controls | `renderCreds`; copy-label test and existing action/portability boundary suites |
| ENV | Variables and risk metadata visible; no value revealed by entering the page | `renderEnv`; workspace visible-row test and existing ENV tests |
| MCP | Visible per-agent declarations and connectivity, with transport/target metadata retained | `renderMcp`; Safari walkthrough and existing page/render checks |
| Traffic | Global comparison; measured zero differs from unknown; canonical resource totals and partial coverage | `renderTraffic`, `google_registry.normalize_document`; workspace and Google identity tests |
| Health | Observer first; three-column desktop diagnostic layout; recovery and review queue retained | `workspace.css`, observer renderer; Safari walkthrough |

The shared navigation groups Work, Infrastructure, Access and System without
concealing routes. Theme controls and route names remain intact. Full metadata
belongs in secondary detail; the primary identity of each inventory row remains
visible. These are product changes recorded in OSS-13–18, not preservation of the
old default-folding assertions.

## Browser and accessibility receipt

The coordinating agent recorded two browser review passes during this run:

1. Safari: all ten split dashboard routes inspected. The review led to shorter
   Overview previews, secondary finding evidence, a seven-column Heroku table and
   a three-column Health layout.
2. Chromium: Projects inspected on desktop and at 390 px in dark theme; full
   detail opened, Escape returned focus, `/` focused search, and narrow-screen
   sorting remained present. Compact mobile navigation exposed all destinations
   in three columns; its inspected height was approximately 235 px. Findings at
   390 px retained visible titles, disclosure exposed evidence and a command,
   and `/` focused its own search. Health labels stacked on narrow screens.
   The second desktop pass covered the seven-column Heroku table and compact
   Overview; switching to light theme and following an exact finding link worked.

These are session observation receipts supplied by the coordinating agent.
Private screenshots and generated operational HTML are intentionally outside the
public repository. They are not reproducible automated screenshots or proof that
every possible record/theme/viewport combination was exercised.

Contrast inspection was limited to the selected token foreground/background
pairs. No screen-reader session, complete WCAG conformance audit, real credential
reveal/rotation or provider mutation was performed. Synthetic command and action
tests verify boundaries; they do not establish live provider acceptance.

## Checks and limits

- `python3 observatory/engine/tests/test_dashboard_shell.py`: six tests passed.
  The original four-test version was also executed against baseline shell code in
  memory and failed in twelve assertions/subtests, with zero execution errors.
- [Workspace renderer tests](../../../observatory/engine/tests/test_workspace_redesign.py)
  exercise visible rows, opposing filters, global traffic order, copy wording,
  warning-only Overview and acknowledged-only history using synthetic data.
- [Google identity tests](../../../observatory/engine/tests/test_google_identity.py)
  contain twelve regression cases covering raw and cached resource identity,
  conflicting measurements, coverage, findings and emitter compatibility.
- All three suites are registered in
  [run_portable.py](../../../observatory/engine/tests/run_portable.py).
  Registration is not itself a passing execution receipt.

The full synthetic portable run passed all 58 suites. The metric-series guard
now parses each source once and still compares every declared metric against
every file. Metric-label assertions open real project detail; the smoke DOM
implements native `Element.remove()`. The following top-level check caught two
stale version literals; both are aligned and all 60 cases pass. The final full
portable rerun timed out in six suites at 120 seconds: all six passed with two
workers and a 300-second timeout. The last footer regression passed eight cases.
The [validation receipt](../../runs/2026-09-26-workspace-redesign/validation.json)
preserves both runs. Wheel inspection passed with 278 runtime/284 archive files.
Privacy passed on 382 files against 3776 private identifier entries. Source
inventory and package checks pass. Final remote verification, protected merge,
release 0.3.12 and installed smoke remain operational delivery steps.

---

**Made with [ssheleg skills](https://github.com/ssheleg/sshlg-skills)**
