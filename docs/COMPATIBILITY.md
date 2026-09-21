# Compatibility and upgrades

The application release is **0.2.0**. The complete engine and each user's workspace are separate. Updating program files never intentionally replaces configuration, registry data, credentials, history or local dashboards. The previously published portable 0.1 command set remains a compatibility entry point; its smaller data model is not interchangeable with the complete engine's SQLite database.

## SQLite runtime prerequisite

The full engine requires Python 3.11+ with SQLite 3.37+ **and loadable SQLite
extensions**, plus the locked sqlite-vec dependency. Some macOS Python builds
omit `enable_load_extension`; installing sqlite-vec alone cannot add it.
Initialization, doctor, migration and upgrade check this before workspace writes.
The isolated regression is
`tests/test_workspace_upgrade.py::WorkspaceUpgrade::test_missing_sqlite_extension_support_refuses_before_writes`.

On macOS, [Homebrew Python](https://formulae.brew.sh/formula/python@3.14)
provides a supported installation path:

```sh
brew install python@3.14
"$(brew --prefix python@3.14)/bin/python3.14" -m venv .venv
. .venv/bin/activate
python -c "import sqlite3; c=sqlite3.connect(':memory:'); c.enable_load_extension(True); c.enable_load_extension(False)"
```

Install the full package and its pinned dependencies in that environment using
the release installation instructions, then run the full doctor command.

## Contracts with separate versions

| Surface | Current supported contract | Change policy |
|---|---|---|
| Workspace | format 1, minimum reader/writer application versions | Refuse unknown formats or newer required versions before writing |
| Main configuration | schema 1 | Preserve unknown optional fields; refuse unsupported `must_understand` capabilities |
| Registry | projects/repositories/relations 1–2; other documents 1 | Refuse future versions; preserve optional top-level extension fields on atomic writes |
| SQLite | seven historical migration IDs, recorded AST checksums | Never rewrite a released migration; append a new ID; upgrade atomically with a verified snapshot |
| Plugin execution | API 1; absent version means legacy API 1 | Reject unknown versions and escaped script paths before execution; plugins remain trusted executable code |
| MCP transport | existing declared 2026-07-28 interface, SDK 2.1.1 | Preserve existing tool names, camelCase/snake_case aliases and proposal authority; transport negotiation is SDK-owned |
| Tool data | existing published input/output schemas | A closed output schema can reject an added field: version the capability before changing its shape |
| CLI | existing full-engine step names plus workspace management | Keep names/arguments through compatible releases; announce deprecation before removal |

Semantic versioning applies to the declared public API even before 1.0 as a project policy. A patch fixes behavior within those contracts. A minor release adds compatible behavior and supported migrations. An intentionally incompatible change needs a major release with migration instructions. This does not promise that every past experimental version remains supported forever; each release publishes its tested upgrade matrix. [SemVer specification](https://semver.org/).

## Tested migration boundary

`observatory/engine/tests/test_schema_compatibility.py` covers every prefix of the seven original migration IDs, repeat opens, legacy checksum adoption, unknown IDs, changed migration checksum, future user_version, rollback after injected failure, WAL-only data and concurrent openers. Adopting a checksum for a legacy history records the current implementation; it cannot prove which old implementation originally ran.

`observatory/engine/tests/test_workspace_boundaries.py` covers concurrent initialization, symbolic-link escape attempts, source changes during migration, future writer refusal and preservation of an existing destination. `observatory/engine/tests/test_workspace.py` covers separate homes, optional settings preservation, configuration/registry version refusal and the complete local pipeline through ten generated pages. Test execution receipts are recorded separately; listing a test here is not a claim that every release ran it.

## Upgrade and rollback rules

1. Read the target release's minimum Python, SQLite and supported source versions. Full engine requires Python 3.11+ and SQLite 3.37+; macOS/Linux are the supported platform family. Windows file-lock/service support is not claimed.
2. Stop the scheduler and other writers. Old executables cannot honor locks or version checks added later. Do not run two application generations against one workspace.
3. Preview the upgrade. Create a complete private snapshot before applying changes, including config and authored data. SQLite backups use its backup API so committed WAL content is included. [SQLite backup documentation](https://www.sqlite.org/backup.html).
4. Apply supported migrations under a lock, validate, then restart the chosen application version. Interrupted upgrades leave a marker that prevents ordinary runtime from treating partial state as healthy.
5. To roll back, restore a verified pre-upgrade snapshot into a separate home and use its matching application release. An older executable must never silently rewrite a newer database. New observations made after the backup are not present in that backup.

External source directories and externally referenced credential stores are **references**, not bundled backup contents. Their independent backup/recovery policy remains the user's responsibility. Internal credential files, when included in a private snapshot, retain private modes and must never be attached to an issue or public release.

## Original installation migration

`migrate-local` previews categories and counts. `--apply --writers-stopped` copies into a new destination; it does not activate services or overwrite the original. Curated owner lists move into private ownership configuration. External paths and integration selection must be verified for the destination before activation. SQLite may update its own SHM bookkeeping during a read-only backup; the promise is preservation of logical source data, not byte-identical auxiliary files.

The full source publication deliberately has no ancestry from a private operational Git repository. Release privacy checks examine source, fixtures, package contents and public history independently from runtime migration tests.
