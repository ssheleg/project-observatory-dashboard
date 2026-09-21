# Portable edition: shipped scope and migration plan

This distribution is a new, independent Git history and a generic implementation of the predecessor's portable concepts. It is **not a sanitized copy of an operational inventory**, and it does not claim parity with the private system. Its first release is useful without accounts: explicit scope → measurements → findings → local dashboard → agent action.

Implementation evidence: [`core.py`](../observatory/core.py), [`credentials.py`](../observatory/credentials.py), [`dashboard.py`](../observatory/dashboard.py), [`cli.py`](../observatory/cli.py), and [runtime tests](../tests/test_observatory.py). The table below is the scope contract; future capabilities are not marketing claims.

## Capability map

| Capability | Portable release | Migration boundary |
|---|---|---|
| Project enrollment | Explicit name + directory; discovery preview | No automatic ownership inference or imported personal registry |
| Local Git state | Branch, dirty-file count, local-ref ahead/behind, upstream, last commit, tags | No remote fetch or full commit-event ingestion; submodules ignored |
| Project metrics | Bounded file count/bytes and root npm dependency counts | No generalized plugin loading, historical charts or build measurements |
| Env inventory | Names, presence, permissions, salted equality fingerprints | Literal dotenv parser; no arbitrary format/service-account discovery |
| Credential storage/use | Local private plaintext slots, stdin/hidden prompt, child env injection | No OS-keychain encryption, remote issuance, automatic rotation or backup |
| Credential exposure | Explicit regular-file/SQLite targets, exact known values, value-free receipts | No automatic session discovery, unknown-pattern detection or memory scrubbing |
| Project findings | Deterministic local findings and actionable remedies | No operator acknowledgement journal, suppression expiry or dependency graph |
| History | Last 100 local observation snapshots in SQLite | No event timeline query, ledger review, erasure protocol or wiki projection |
| Dashboard | Read-only overview, findings, synthetic demo, credential-exposure summary | No authenticated admin mutations, multi-page management console or charts |
| Agent entry | Documented CLI and onboarding prompt | No installed session hooks, MCP server or persistent agent daemon |
| External providers | None required or called | Cloud hosting, analytics, DNS, provider key state and billing are future opt-in adapters |
| Agent reasoning | Agent consumes measured CLI results | No paid model execution, automatic conclusions or budget wallet |
| Coordination | Explicit user-owned scope, atomic state-file writes | Concurrent config writers are not supported; no agent-sync lease integration yet |
| Sharing | Aggregate export, synthetic site, generic docs | No public inventory, real dashboard, private source history or raw receipts |

## Scenarios and current acceptance evidence

- **S1 — First useful view:** a newcomer runs demo without keys or network and sees one fictional project and two explicitly synthetic exposure occurrences. `test_complete_cli_demo_is_synthetic`.
- **S2 — Controlled scope:** discovery previews candidates; only add enrolls. Symlinks cannot silently widen a registered root later. `test_discovery_does_not_register_or_follow_symlinks`, `test_registered_root_replaced_by_symlink_is_refused`.
- **S3 — Unpublished work:** a local bare-remote fixture develops one ahead commit and one dirty file, observed without fetching. `test_git_real_workflow_reports_ahead_without_network`.
- **S4 — Metadata without values:** environment metadata and same-installation equality survive; values and known-value metadata echoes are absent. `test_env_only_metadata_salted_per_installation`, `test_metadata_canary_redacted_in_names_paths_and_slot_labels`.
- **S5 — Deliberate local secret use:** stdin storage, names-only listing and an explicit child command do not echo values. `test_secret_stdin_and_child_output_suppressed`.
- **S6 — Local exposure evidence:** a selected file/SQLite yields exact counts and opaque target identifiers, with no content or path serialization. `test_known_value_file_scan_no_content_or_paths`, `test_sqlite_scan_is_readonly_and_quotes_identifiers`.
- **S7 — Honest limits:** unavailable scope, no known values and generated SQLite columns are partial/degraded, not all-clear. Corresponding missing-root, no-known-values and generated-payload tests.
- **S8 — Share an aggregate:** exported data contains counts, a validated timestamp and no project names/paths/fingerprints; malformed snapshot fields are refused. `test_export_refuses_untyped_snapshot_fields`.
- **S9 — Safe local view:** script text is escaped; unexpected Host/Origin and POST are refused. `test_dashboard_escapes_and_omits_credentials`, `test_http_rejects_rebinding_origin_prefix_and_writes`.

## Sequenced backlog with acceptance criteria

These are bounded packets. Priorities indicate recommended order, not claims of delivery. Each packet updates scenarios, docs and negative tests in its own change.

| ID / priority | Work and dependencies | Acceptance criteria | Security and UX requirement |
|---|---|---|---|
| M01 / P1 | Editable enrollment and concurrency; depends on current explicit config | `project remove` and rename preserve past observations; two concurrent add operations either merge safely or one fails with a clear conflict; migration version and rollback test | Preview scope diff; no implicit deletion of source or secret slots; transactional locking |
| M02 / P1 | History query and project detail; depends on M01 stable IDs | Query snapshots by stable project ID/date; compare two scans; expose change provenance and partial inputs; retention semantics tested | First screen distinguishes current state, old snapshot and unavailable source; identifiers remain local |
| M03 / P1 | Credential references and OS keychain adapter | Slot metadata has purpose/scope without values; injected child uses chosen backend; mock and native optional tests; rotation/revocation are explicit | Never return values through MCP/HTTP/chat; fail closed when keychain locked; plaintext remains an explicitly chosen backend |
| M04 / P1 | Findings lifecycle | Acknowledge with reason, expiry and source evidence; reappearance produces a new episode; dismissed is distinct from resolved | No agent self-approval; unreadable acknowledgement state is a finding, not empty success |
| M05 / P1 | Bounded streaming and exposure target profiles | Large regular files stream with correct chunk overlap; SQLite byte/time/table limits; opt-in named target profiles; duplicates do not inflate unique metrics | Show scan coverage and skipped data; no default whole-home traversal; no snippets; causal claims separated from observations |
| M06 / shipped, extend per release | Public privacy release gate; [`tools/check_public_release.py`](../tools/check_public_release.py), synthetic positive/negative test, [release receipt](RELEASE.md) | Current tree allowlist, token-shape + optional private-identifier checks and full-ref blob scan; extend allowed types/rules only with negative tests when scope expands | No private values or matched identifiers in scan output; fail publication on unknown files; original repo stays private |
| M07 / P2 | Metrics adapter API; depends on M02 | Versioned input/output schema, deterministic bounded plugins, synthetic tests for disk/dependency/releases; timeouts and degraded receipts | Explicit plugin allowlist; no arbitrary imported code by manifest alone; chart states explain missing data |
| M08 / P2 | Remote Git inventory/freshness; depends on M01/M04 | Opt-in GitHub/Bitbucket adapters with pagination, rate-limit and permission fixtures; fetch freshness separated from local refs | Least-privilege read scopes; authenticated ownership evidence, never name guesses; no commit/push from a scan |
| M09 / P2 | Hosting and domain adapters; depends on M07/M08 | Opt-in hosting/DNS snapshots with identity/state/cost provenance, staleness rules and unlinked items; currencies/date ranges explicit | No registrar authorization codes, raw provider responses or API tokens persisted; local keys configured by agent-guided instructions |
| M10 / P2 | Analytics adapters; depends on M07/M09 | GA4/search/traffic measurements link through declared host/app identifiers; cached read scope and quota tests; unknown ownership remains unknown | Explicit account selection; no private property names in public reports; window/unit definitions accompany metrics |
| M11 / P2 | MCP read/proposal contract; depends on M02/M04 | Public synthetic contract fixtures; status/project/timeline/findings tools; invalid scope and stale-version tests; backward compatibility receipt | Metadata only; no HTTP reveal/provision; agent proposals cannot overwrite operator approvals; OAuth direct-client boundary respected |
| M12 / P2 | Agent observations and budget ledger; depends on M02/M04/M11 | Optional provider interface, deterministic fixture replay, per-run/day spend caps, provenance and expiry; failures produce receipts | Disabled by default; estimated vs actual spend separated; conclusions proposed with confidence, never auto-approved |
| M13 / P2 | Scheduler and session hooks; depends on M01/M04/M11 | Explicit install/uninstall/status for supported OS; idempotent cycle; overlap lease; observable heartbeat; no writes when lock unavailable | Explain provider/network/spend effects before enablement; no SessionStart action beyond declared scope; no unsolicited notifications |
| M14 / P3 | Safe optional remediation | Separate design and dry-run preview for provider rotation and third-party-store cleanup; owner-approved action receipt; rollback/backup plan; failure propagation | Never ship automatic memory scrubbing as a side effect of scan; deleting copies is not revocation; backups remain sensitive |
| M15 / P3 | Full operational UI; depends on M02–M04/M07 | Project detail, metrics history, finding filters, keyboard-first navigation, useful empty states, responsive tables and accessible focus/contrast | Read/admin modes distinct; no secret reveals; actions show exact scope/result; browser validation supplements assertions |
| M16 / P3 | Wiki projection and recovery export; depends on M02/M11 | Versioned generated projection with source IDs; drift/ownership checks; tested restore into empty state; selective export policy | Narrative is not silently overwritten; local paths/identifiers never become public documentation; backup excludes values unless user explicitly chooses protected credential recovery |

M06 is required again before each expanded distribution. M03/M11/M14 require a dedicated security review. A cloud API adapter cannot be marked complete by documenting an environment variable alone.

## What must never migrate

Do not migrate private repository history, inventory registries, operational Markdown/audits, real provider exports, database journals, local config, credential files, historical fixtures carrying actual project identities, screenshots or personal machine paths. A new public file starts from generic source and synthetic fixtures. This distribution contains no bundled copy of those artifacts.

## UI follow-up sequence

First make the existing overview useful on one narrow viewport and with keyboard navigation. Next add project detail and history with a stable ID (M02), then finding lifecycle (M04). Only after those information paths are clear should charts or administrative actions be added. Validate first-run, empty, partial, stale, many-project and one-critical-finding states in a browser. Keep implementation jargon out of the operator path; show the action, scope and evidence.
