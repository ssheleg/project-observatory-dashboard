# Changelog

All notable changes to Project Observatory. Versions follow [semantic versioning](https://semver.org/);
while the major version is 0, a minor release may change behaviour and says so here.

## Unreleased

### Fixed

- The scheduled tick and the plugin hooks run with the Python that installed the engine
  (`OBSERVATORY_PYTHON`, written by `install_launchd.py` and `full agent install`). An installed
  package has no `.venv`, so tick fell back to the first `python3` on PATH, which lacks the `[full]`
  dependencies: the vector index reported "sqlite-vec is not loadable here". Companion plugin 0.11.1.

## 0.2.4 — 2026-09-23

### Changed

- The engine's comments and docstrings are back: 3,049 lines restored from the original sources
  that the first public export had blanked, filtered for private identifiers, with every file's
  syntax tree unchanged.

### Added

- `full doctor` reports `coverage_warnings`: an enabled integration or feature whose source is not
  configured or does not exist. A migrated installation without a `sessions` source had its leak
  scan narrowed from every agent transcript to four files without any warning. ONBOARDING now lists
  every source.

## 0.2.3 — 2026-09-23

### Fixed

- launchd jobs written by `install_launchd.py` and `serverd.py --install` carry the installing
  user's safe `PATH` directories, so collectors find `claude`, `heroku` and similar tools installed
  outside the system directories; before, the MCP inventory degraded with "claude CLI not on PATH".

## 0.2.2 — 2026-09-23

### Fixed

- **`full migrate-local` works again for installations that have a fingerprint salt or keyserver
  token.** 0.2.1 created fresh identities while staging the new workspace and then refused to copy
  the originals over them, so the migration stopped (`File exists`) and nothing was written. The
  original identities now move unchanged, and only a missing one is created, so fingerprints stay
  comparable across the move.
- Two processes opening a new database at the same moment no longer fail one of them with a
  `DatabaseError`: the version check that runs before the upgrade lock ignores a file another
  process is still creating, and the check under the lock decides.

## 0.2.1 — 2026-09-23

A correctness and security release. An audit of the published 0.2.0 wheel found fixes that had been
made in the private predecessor but never reached the public engine. All of them are carried here,
each with a regression test that fails on 0.2.0.

### Security

- **A local `rotate` no longer marks a leaked credential as closed.** In 0.2.0, `vault.py rotate`
  settled every open leak of the slot it replaced, although replacing a local slot proves neither
  that the provider revoked the old value nor that its consumers moved. `settle` (and
  `moved --settle`) now require `--revocation-evidence` and `--consumer-evidence`, recorded as manual
  attestations. **Upgrading reopens** every leak that 0.2.0 closed only by a local rotate: it shows
  as "closed only by a local rotate" at warning severity until you settle it with evidence.
- **The fingerprint salt and keyserver token are never created by a read.** A missing, empty,
  malformed, loosely permissioned or symlinked identity file is refused and left untouched.
  Identities are created only by `full init` (race-free), and re-running `full init` on an existing
  workspace keeps them and restores only a missing one.
- **Fingerprints taken under different salts are not compared.** Scans record a
  `fingerprint_namespace`; a comparison across namespaces answers `not_compared` with a
  `namespace_withheld` finding instead of a misleading "differs".
- **A private home inside the installed code or its checkout is refused.** 0.2.0 accepted an
  `OBSERVATORY_HOME` inside `site-packages`, where an upgrade or uninstall deletes it, or inside a
  source checkout, where it can be committed.

### Fixed

- A corrupt `finding_acks.json` is preserved: `ack` refuses to write, and the board builds without
  acknowledgements and names the unreadable file, instead of overwriting every saved decision.
- A former project id claimed by two projects is left unresolved rather than handing one project's
  history to the other by row order.
- A session that matches two projects equally is left unattributed (`ambiguous-project`) instead of
  being credited to whichever came first; a stale link is withdrawn by an event.
- The dashboard reads wallet and provider health from `OBSERVATORY_STATE`, where providers write
  them; ENV-page filters open the matching groups; counts use correct plural forms.
- The dashboard root `/` redirects to `/dashboard/index.html`, so its stylesheet and script load.
  Served at `/`, 0.2.0's pages opened unstyled and without data.

### Added

- `project-observatory full open [--serve]` builds the dashboard if needed and opens it, as local
  files or from the loopback server; it refuses to reuse a port that serves another workspace.
- `project-observatory full agent install|status|uninstall` installs the `observatory-log` Claude
  Code plugin from this repository with **auto-update on by default** (`--no-auto-update` opts out)
  and points its hooks at your workspace. The repository root is now a plugin marketplace.
- `tools/update_inventory.py` keeps the engine source inventory current; CI runs it with `--check`.
- CI installs the built wheel without the lock file and runs the dependency-sensitive suites.
- New regression suites: audit regressions, runtime identity, remote env, project identity,
  sessions, ENV page, metric labels, agent plugin.

### Upgrade

```sh
python -m pip install -U -c requirements-full.lock '.[full]'   # or the 0.2.1 release wheel
project-observatory full upgrade                                # preview, then --apply --writers-stopped
project-observatory full init                                   # creates any missing runtime identity
project-observatory full agent install                          # optional: plugin with auto-update
```

A 0.2.0 workspace is read by 0.2.1 as it is. A workspace created by 0.2.1 records 0.2.1 as its minimum reader.
The companion plugin is 0.11.0.

### Not established by this release

Live provider revocation and rotation, admission by external MCP hosts, and off-device restore were
not exercised; checks run on synthetic offline fixtures. Known-value scanning cannot prove that no
secret remains.

## 0.2.0 — 2026-09-21

First public release of the complete engine. See [docs/RELEASE.md](docs/RELEASE.md).

## 0.1.0

Portable CLI. See [docs/RELEASE-0.1.md](docs/RELEASE-0.1.md).
