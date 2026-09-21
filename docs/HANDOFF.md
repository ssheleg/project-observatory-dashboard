# Public distribution handoff

Objective: publish a useful, generic local observation component of the ssheleg harness without exposing an operational inventory, credentials or private source history.

The public tree contains a standalone standard-library Python CLI, explicit project scope, local Git/file/env metadata, deterministic findings, private snapshot history, a read-only dashboard, local stdin-based secret slots, bounded known-value file/SQLite checks, aggregate exports and synthetic tests. Installation and agent onboarding are in [ONBOARDING.md](ONBOARDING.md); the exact feature gap and next packets are in [MIGRATION.md](MIGRATION.md).

Decisions: use a new repository root; keep the original deployment private and intact; ship portable functionality with explicit limits; require no accounts for the first useful view; do not imply provider integrations or automatic remediation are included. The threat model is [SECURITY.md](../SECURITY.md). The public website in `site/` and private generated dashboard are different artifacts.

Checks to run from a fresh checkout:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install .
python -m unittest discover -s tests -v
project-observatory --home "$HOME/.local/share/observatory-fresh-demo" demo
project-observatory --home "$HOME/.local/share/observatory-fresh-demo" doctor
```

Runtime tests cover synthetic first run, local Git ahead/dirty state, malicious Git clean filters, symlink scope changes, metadata redaction, private-file modes, read-only SQLite and generated-column bounds, invalid export state and HTTP Host/Origin controls. No live provider or real credential verification is implied by those tests. Test execution results belong in the release receipt/CI, not a hard-coded permanent assertion count.

Prerequisites: Python 3.11+, optional Git, local macOS/Linux shell. Remote publication and static-site deployment are verified by the release owner after final full-tree privacy review. No existing repository should be made public to complete that release.

Exact next development task after the portable release: M01, transactional project enrollment and removal with stable identity, followed by M02 history query/project detail. Read the acceptance criteria and related scenarios before implementation. Provider, MCP and scheduler work remains explicitly pending; do not reconstruct the feature boundary from chat.
