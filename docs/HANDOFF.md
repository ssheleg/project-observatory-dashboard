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

## Published release and deployment

- [0.2.0 release](https://github.com/ssheleg/project-observatory-open-source/releases/tag/v0.2.0): source `fb8d692416da63323d29ae4f89ab71f5c5ba3faa`, inspected wheel and SHA256SUMS. Downloaded release assets match the reviewed archive.
- [Engine CI](https://github.com/ssheleg/project-observatory-open-source/actions/runs/35599940689): Linux Python 3.11/3.14 and macOS Python 3.14 all pass.
- [Website compatibility correction](https://github.com/ssheleg/project-observatory-open-source/commit/c773b5d483a75e7c79fce520a97d4a85c1d6a300): content-versioned CSS/JS prevents previous browser caches breaking new pages; eight static negative probes pass. [CI](https://github.com/ssheleg/project-observatory-open-source/actions/runs/35600519090) passes all platforms.
- [Production](https://observatory.sshlg.me/) and [article](https://observatory.sshlg.me/field-notes/): deployed website commit above, Cloudflare deployment `6a319bfa-aa59-48a3-ad31-4843a1809c64`. Ten served files match source bytes; the eleventh file supplies verified response headers.
- Both pages checked at 320px and 1440px with no overflow, including the previously cached browser. Copy and before/after actions work; no console warnings/errors.

[Machine receipt](releases/0.2.0.json) separates package source, website source,
CI, asset digests and deployment. The website-only fix did not change the wheel.
This follow-up changes documentation only and does not imply another deployment.

## Next task and prerequisites

Release work is complete. A new operator starts with [agent onboarding](AGENT-ONBOARDING.md)
in a private workspace; real provider permissions are checked against their own
accounts only after explicit enablement. Future interface improvements are bounded
in [UI-PLAN.md](ux/UI-PLAN.md). Existing live installations need a deliberate
backup/root/home migration and host restart; no implicit switch was made here.
Social drafts remain unpublished. Preserve the local-only rule above.

## Latest editorial delivery

The Claude Code credential-copy article and channel posts were revised and the
website redeployed. See the [editorial handoff](runs/2026-09-21-credential-copy-editorial.md)
for its source revision, checks and deployment; the package release above is unchanged.

## Latest owner-origin article delivery

The field-notes article now tells the owner's path from project inventory and
revival to repeated key warnings and monitoring. The
[origin-story handoff](runs/2026-09-21-observatory-origin-story.md) supersedes the
previous article wording and contains its source ledger, validation and production
receipt. The canonical URL is unchanged. Social posts remain unpublished drafts.

## Illustrated reading and SEO update

[Latest bounded handoff](runs/2026-09-21-reading-seo.md) records the cross-site article, reading and search work, checks and delivery status.
