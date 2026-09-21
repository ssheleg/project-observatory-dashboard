# Full engine 0.2.0 verification

Measured on 2026-09-21. This receipt covers the reviewed public engine, synthetic
runtime checks, package installation and public website. It is not a certification
that every secret or vulnerability is detectable. Remote CI and production receipts
are added to the release handoff after integration.

## Source and package

The public engine inventory contains 228 files, including 160 Python files. The
source export was checked against 302 private identifiers with zero findings.
All 115 original runtime Python modules were retained; generic helpers, contracts
and tests are additional. Private operational Git history was not imported.
[Source inventory](../observatory/engine/SOURCE-INVENTORY.json).

The inspected `project_observatory-0.2.0-py3-none-any.whl` has 236 runtime files and
242 total archive entries. Runtime bytes match the source inventory and launcher.
SHA-256: `2627bfdbbc50fa466b74888fc7ce3eafc7eab825f86523c0b7f1f51a7bdd2327`.
ZIP timestamps can change a subsequent build's digest; each released artifact must
pass the package checker again. No private workspace or public marketing image is
inside the wheel.

## Checks actually run

| Check | Observed result | Boundary |
|---|---|---|
| Full engine `full check` on exported source | 33/33 suites PASS, 854 assertion checks and 166 unittest cases,zero skipped suites | Synthetic offline sources; Python 3.14.7/macOS |
| Root compatibility/launcher/release-gate tests | 42 unittest cases PASS | Old 0.1 CLI and full launcher separation |
| Source exporter regressions | 14 PASS | Explicit docs/profile inclusion, source sanitization/allowlist |
| Archive verification | 236 runtime entries, 242 total,byte-exact | Hardened checker PASS, including RECORD integrity and exact metadata allowlist |
| Fresh virtual environment installed from wheel and locked full dependencies | `init`, `configure sources projects`, `local`, `doctor`, `upgrade` preview all exit 0 | Separate synthetic workspace, database integrity PASS, no provider calls |
| Export unchanged after tests | 0 changed,missing or extra engine files | 228 inventory entries compared |
| Companion skills | Both skill audits 18 PASS/0 GAP; both strict plugin validations PASS | `observatory-log` 0.10.0; host runtime not globally reconfigured |
| Static site gate | 11 reviewed files, 6 negative probes PASS | Local references, required scope, aggregate arithmetic, image digest |
| Browser | Landing/article at 320px and 1440px, no document overflow; toggle/copy/keyboard skip work; no console warnings/errors | Reviewed public flows, not a full accessibility certification |
| Brand contract | 0 errors; 310 warnings | Whole-engine literal extraction includes SQL and unregistered inherited strings; no claim of full copy registration |

A private migration rehearsal independently verified a copied original database and
registries through migration and backup/restore. No live installation was switched,
no scheduler was activated, and detailed private evidence was not published.

## Fixes covered by this release

Per-user source/state separation; safe registry/schema/version handling; migration
backups including committed WAL data; staged upgrade/restore and recovery markers;
workspace-specific scheduling; strict loopback Host/Origin checks; atomic private
secret writes and streaming known-value filtering; failure-aware provider rotation;
portable copied dashboard commands; explicit offline test selection; package resource
completeness. Tests exercise failures as well as successful paths.

## What this does not establish

Live provider permissions, remote credential rotation and admission by external
agent hosts were not exercised. Optional model calls and remediation stay disabled
until an operator chooses them. Original private services remain unchanged.
Known-value scanning does not establish that no secret remains. Full default slots
are private plaintext files; the authenticated local reveal operation still exists.

Read [COMPATIBILITY.md](COMPATIBILITY.md), [SECURITY.md](../SECURITY.md) and the
[0.1 historical receipt](RELEASE-0.1.md) for the separate compatibility runtime.

Final public tree/history check: 294 files and 43 historical blobs, 302 private identifiers,zero findings before this source commit. Ten additional negative tests cover filename/case privacy, image tamper/history and wheel metadata/symlink/RECORD boundaries. The gate is repeated on the committed public history in CI.
