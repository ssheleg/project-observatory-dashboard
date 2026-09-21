# Product scenarios by runtime

This file indexes the two distinct runtime paths. The table below describes the retained portable compatibility CLI only. Full-engine scenarios are in [portable-scenarios.md](../../observatory/engine/docs/ux/portable-scenarios.md); despite that historical filename, its OSS scenarios cover the full engine. The public site's scenarios live separately in [docs/site/](../site/). The implementation and tests are linked from [MIGRATION.md](../MIGRATION.md).

| ID | User and trigger | Path and successful outcome | Current state / evidence |
|---|---|---|---|
| O1 | New operator wants to understand the tool before granting access | Install → synthetic demo → local overview → explicit explanation of scope and limits | Shipped; `test_complete_cli_demo_is_synthetic` |
| O2 | Operator has many folders but has not chosen ownership | Discover inside a chosen root → preview candidates → add individual authorized directories → first scan | Shipped CLI; discovery never enrolls; symlink boundary regression |
| O3 | Agent needs to know what work is not saved remotely | Scan → project Git metadata → ahead/dirty/no-upstream finding → remedy with local-ref freshness caveat | Shipped; synthetic bare-remote E2E test; no automatic push |
| O4 | Operator wants to locate risky environment handling | Scan → variable names and equality fingerprints → permission finding → explicit local action | Shipped CLI; private metadata, never env values; same-installation equality only |
| O5 | Agent needs one credential for an authorized command | Operator enters through hidden local prompt/stdin → list label → inject into an explicit child → exit status | Shipped; child output suppressed; no reveal route |
| O6 | Operator suspects a copied value in a log or memory store | Select known slot(s) and explicit target → exact match → opaque target label and occurrence count → issuer/artifact review | Shipped file/SQLite checker; no automatic scrub or rotation |
| O7 | A source is absent, unreadable, stale or bounded | Observe → visible partial status, skipped coverage and last scan time → repair scope/retry | Shipped degradation and timestamp; automatic age-based stale warning not yet shipped |
| O8 | Operator shares progress with someone outside the machine | Aggregate export → explicit human review → share selected counts | Shipped; identifiers/fingerprints omitted; counts still may be sensitive |
| O9 | Operator returns later to inspect the estate | Open loopback overview → find project and next action → repeat scan in CLI | Shipped read-only overview; detail/history/filter screens are planned |

Cross-scenario constraints: no hidden enrollment, unknown ownership remains unknown, no value in chat, no provider request without a separately implemented opt-in, no administrative mutation from the dashboard, and no deployment of generated private HTML.

The next UI work is [UI-PLAN.md](UI-PLAN.md), with explicit done conditions. Update this file in the same change as any new user path.
