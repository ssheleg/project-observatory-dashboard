# Full-system release handoff

Objective: distribute the complete Project Observatory engine as open source while
each user retains their own private projects, credentials and runtime state; retain
older CLI contracts, provide future upgrade/restore safeguards, and publish accurate
onboarding, website and launch material.

## Completed implementation

- Complete source export under `observatory/engine/`; generic defaults, individual
  integration/feature opt-ins, explicit per-user source paths and private workspace.
- Original portable CLI preserved. Full engine enters through `full`; homes and
  formats remain distinct. Versioned config/workspace/registry/database/plugin/tool
  contracts, supported migration checks, backup/apply/restore and unknown-version
  refusal are documented in [COMPATIBILITY.md](COMPATIBILITY.md).
- Full engine source and installed-wheel synthetic checks completed; receipt in
  [RELEASE.md](RELEASE.md). CI repeats on Linux 3.11/3.14 and macOS 3.14.
- Credential/keyserver/provider failure fixes and portable dashboard commands.
- Public site describes the full release; canonical [article](../site/field-notes/index.html),
  generated cover and [social drafts](content/README.md). Social accounts were not posted to.
- Skills remains the family site's primary entry. Harness is its separate section;
  Observatory observes projects, Asset Foundry is explicitly in development.

## Module and task packets

[Migration/capability map](MIGRATION.md), [agent onboarding](AGENT-ONBOARDING.md),
[product scenarios](ux/scenarios.md), [next UX packets](ux/UI-PLAN.md),
[site scenarios](site/BRIEF.md), [deployment procedure](site/DEPLOY.md),
[case-study boundaries](site/CASE-STUDY.md), [security policy](../SECURITY.md).

## Local-only rule

Never add a real workspace, database, private denylist, registry, credentials,
operational receipt, provider response or local machine configuration to this
repository. Never deploy generated private dashboard pages. The public source has
no private operational ancestry. Original installed services were not switched.

## Release completion

At this source checkpoint, commit/push, remote CI, integration, release assets and
production deployments remain a release-owner task. Record their exact commits,
run/deployment IDs and verified URLs in a follow-up receipt. A pushed branch alone
is not a release. Use the reviewed static `site/` artifact for Cloudflare Pages;
Skills is served by GitHub Pages and the personal site has its own Cloudflare job.

Exact next task: run final public tree/history+302identifier gate and package
negative tests, commit/push this branch, wait for all supported CI jobs, then
integrate and publish 0.2.0. Verify a fresh checkout and live article before calling
the release delivered. Keep social drafts unpublished unless explicitly asked.
