# Contributing

Start with the [onboarding](docs/ONBOARDING.md), [compatibility policy](docs/COMPATIBILITY.md)
and [security boundary](SECURITY.md). Code, tests and defaults must be usable
without the author's accounts, projects or paths.

```sh
python -m pip install -c requirements-full.lock '.[full]'
python -m unittest discover -s tests -v
project-observatory full check
python tools/check_public_release.py --history
python docs/site/check.py --self-test
```

Use synthetic fixtures and isolated temporary workspaces. Never run the full
historical test directory indiscriminately against an operational home. The
portable runner lists its supported suites and labels live provider checks
separately. Tests must not depend on personal credentials or project inventory.

Do not alter a released database migration in place: add a migration, preserve
existing IDs/checksums, and test supported prefixes, rollback, WAL data and
future-version refusal. Preserve unknown optional configuration fields. Changes
to MCP input/output schemas and metric plugin requirements need explicit
compatibility tests. Keep the old portable command namespace working.

A change to the complete engine updates its source inventory in the same review.
The initial inventory also records the sanitized extraction from its private
predecessor; never copy that predecessor's Git history or operational documents.
Dependency constraint updates require the Python/OS CI matrix, not just a local
import check. Build a wheel and run `tools/check_package.py` against it.

Update scenarios, onboarding and documentation with behavior. Keep unsupported
features and unexecuted tests clearly labelled. Public copy must cite reviewed
facts and never turn occurrence counts into unique-secret or breach counts.
New public assets require an explicit path and content review before entering
the release allowlist.
