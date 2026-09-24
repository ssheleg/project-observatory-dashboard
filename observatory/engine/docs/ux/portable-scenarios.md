# Full-system installation and compatibility scenarios

These supplement the original product scenarios. Approved scope: operator requested full migration, per-user private configuration, future backwards compatibility and autonomous implementation. Product outcomes remain unobserved until a real installation walkthrough.

| ID | User goal | Observable result | Recovery and invariant |
|---|---|---|---|
| OSS-01 | Install on a new machine | init creates a private versioned home; doctor needs no credentials or network | Unsupported format fails before writes; re-running init preserves settings |
| OSS-02 | Add my project directory | Explicit absolute source path is recorded; filesystem scan reads it | No implicit home-directory traversal; missing source is reported |
| OSS-03 | Connect an external service | Agent explains permissions; local secret input; status shows no value | Integration remains disabled until chosen; credential errors remain local |
| OSS-04 | Bring my existing installation | Preview reports categories/counts; apply creates a separate copy, source remains usable | Changed source, symlink or unreadable data aborts; original is not overwritten |
| OSS-05 | Upgrade | Supported legacy schema upgrades atomically with a WAL-aware backup | Unknown newer format is refused before mutation; failed migration rolls back |
| OSS-06 | Return to the previous release | Restore a complete snapshot into a separate home and use its matching code | Never run an old writer against a newer schema; no silent database downgrade |
| OSS-07 | Keep old agent clients working | Existing MCP tool names and supported schemas stay available | Breaking tool changes require a new version; unknown required capability is refused |
| OSS-08 | Schedule observations | Explicitly enabled job carries the chosen workspace and no secret values | One writer per workspace; existing installation jobs are not replaced silently |
| OSS-09 | Open the credential UI locally | Correct loopback Host/Origin accepted; authenticated operation logged without secret values | Lookalike origins, DNS rebinding and malformed requests are refused before effects |
| OSS-10 | Copy a command from the local dashboard | Absolute program paths and Python select the displayed workspace; project and secret roots can contain spaces and quotes | Arguments remain literal, including shell metacharacters; static ENV actions locate a named slot without printing its value; importing a value requires an explicitly chosen private input file |
| OSS-11 | See what a project runs where | The projects table groups each project's apps by the environment they serve. Production comes first, and the account is shown on hover. An app no override or provider placed in an environment is shown as not specified | Never inferred from an app's name. `config/environments.json` places an app, and `tests/test_hosting_groups.py` covers the grouping |
| OSS-12 | Act on a key from the live dashboard | A refusal the server explains says "не вышло" (failed) with its reason, and the action can be retried. A timeout, a dropped connection, an unreadable answer or a server fault says "исход неизвестен · проверьте" (outcome unknown, check) and locks the button | A repeat after a lost answer could mint or revoke twice, so the button stays locked until a rescan shows what happened. Covered by `tests/test_action_outcomes.py` |

OSS-10 regression evidence: `tests/test_dashboard_portability.py` executes generated
commands against inert synthetic tools from an unrelated working directory. Nine
tests cover workspace selection, quoted provider names and movement evidence,
configured secret/project paths, static ENV lookup, missing-project refusal, and
platform-neutral private-file input. This verifies command behavior, not visual
layout or a live credential operation.

For the observer status card, the portable command starts the server explicitly in
the foreground or checks its heartbeat. It does not address a historical launchd
label or silently install a background job. The onboarding flow separately owns
opt-in scheduler installation. Empty-state observation uses `local`; Google refresh
uses its collector's supported `--force` option and rebuilds the registry before
the dashboard. `tests/test_pages.py` checks the command bridges and actual tool
subcommands; `tests/test_dashboard_render.py` executes the renderer.
