# Install the complete Project Observatory

The public package contains the original engine with per-user paths and generic
configuration. Its database, registries, keys and generated pages live in a
private workspace outside the installed source. macOS and Linux are supported;
Python 3.11+, SQLite 3.37+, Git and Node.js are required for the complete local
checks. The Python package's `full` extra installs the MCP, schema, vector-store
and Google authentication libraries at the versions tested by this release.

## SQLite runtime prerequisite

The full engine requires Python 3.11+ with SQLite 3.37+ **and loadable SQLite
extensions**, plus the locked sqlite-vec dependency. Some macOS Python builds
omit `enable_load_extension`; installing sqlite-vec alone cannot add it.
Initialization, doctor, migration and upgrade check this before workspace writes.
The isolated regression is
`observatory/engine/tests/test_workspace_upgrade.py::WorkspaceUpgrade::test_missing_sqlite_extension_support_refuses_before_writes`.

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

## Start without credentials

From a checkout of the public release:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -c requirements-full.lock '.[full]'
export OBSERVATORY_HOME="$HOME/.local/share/project-observatory-full"
project-observatory full version
project-observatory full init
project-observatory full doctor
project-observatory full configure sources projects "$HOME/projects"
project-observatory full local
```

Choose an existing project directory you own instead of the example
`$HOME/projects`. The directory is an explicit observation boundary; the scanner
reads its project metadata and Git history. Do not point it at a directory that
you are not authorized to inspect. `local` invokes no external provider or
arbitrary plugin. Inspect the generated `docs/dashboard/index.html` beneath
`OBSERVATORY_HOME`. These pages contain private project information. They do not
belong on the public marketing website.

`init` is idempotent. It seeds missing initial state only for an empty new home;
it does not replace an existing installation. Configuration belongs in
`config/settings.json`; curated overrides and policy files are adjacent.
`project-observatory full-path` prints the immutable engine directory, useful
for connecting scripts, hooks and MCP.

The old 0.1 commands remain available without `full`. They use their previous
workspace format and previous default home. Do not combine the two formats.
`OBSERVATORY_FULL_HOME`, when set, selects the full launcher home ahead of
`OBSERVATORY_HOME`; an explicit global `--home` takes precedence over both.
Always pass the same home to the CLI, server and scheduler.

## Give this prompt to your agent

Copy [AGENT-ONBOARDING.md](AGENT-ONBOARDING.md), or run
`project-observatory full onboard`. The agent starts locally, explains available
integrations, and guides credential entry on your own machine. It does not need
the author's accounts or data.

## Choose integrations individually

List current settings with `doctor`. Enable a selected integration with
`project-observatory full configure integrations NAME true`. The collector's
installed help and source describe its exact input format. Start with the
smallest account access that can read the requested resources; inventory access
and token provisioning are different permissions.

| Integration name | Purpose | User-owned setup |
|---|---|---|
| `github` | Repository inventory | Authenticate GitHub CLI locally; it enumerates resources visible to that account |
| `bitbucket` | Repository inventory | A local Bitbucket credential in the configured secret store |
| `cloudflare` | Zones and DNS inventory | User-owned account credentials; token administration is separately scoped |
| `heroku` | Hosting inventory | Local authentication for the intended Heroku account |
| `google` | Analytics property and search inventory | The user's service account files and resource grants |
| `domains` | Domain observations | Explicit domain export and network access |
| `mcp` | Configured server inventory | Explicit `sources.mcp_config_root` |
| `sessions` | Local agent activity | Explicit `sources.sessions` |
| `wiki` | Knowledge-base inventory | Explicit `sources.wiki` |
| `openrouter` | Key and usage inventory | A locally supplied provider credential |
| `remote_env` | Compare deployed environment metadata | Explicit opt-in to provider environment reads |

Metric plugins have their own manifest requirements and opt-ins. Run
`project-observatory full plugins-check` to validate them and read
[plugins/README.md](../observatory/engine/plugins/README.md) before adding trusted executable plugins.
An unavailable input must remain visible as unavailable; it does not prove that
there are no findings.

## Enter credentials locally

For project slots, the full engine's `tools/vault.py put PROJECT ENV NAME`
accepts the value only on stdin. Prefer a human-controlled hidden prompt or a
pipe from an already authenticated provider tool. Do not put a secret in a chat,
command argument, test fixture or tracked file. Read the installed
`handling-secrets` skill before an agent works with these commands.

Slots are private files under the workspace by default. A separate
`sources.secret_store` is optional and belongs to the user. File permissions
limit local access; this is not a claim that the default files are encrypted at
rest. Protect private backups just as carefully. A configured external store
is not included in workspace backup snapshots.

Known-value scanning finds occurrences of values already known locally. It
cannot prove the absence of unknown, encoded or previously deleted values.
Rotation changes the local slot; provider revocation is a separate action.

## Connect an agent

The complete MCP server uses stdio. Configure a Python executable from the
installed virtual environment, the engine's `mcp/server.py` as its argument,
and `OBSERVATORY_HOME` for the selected private workspace. Detect MCP support
in the chosen agent rather than assuming it from the product name. The optional
`observatory-log` plugin adds Claude Code hooks; other hosts can use the CLI
and MCP without those hooks.

For Claude Code, run `project-observatory full agent install`. It adds the
GitHub marketplace `ssheleg/project-observatory-dashboard`, installs
`observatory-log@observatory-log`, turns plugin auto-update on (opt out with
`--no-auto-update`) and writes `OBSERVATORY_ROOT` and `OBSERVATORY_HOME` into
Claude Code's user settings for the hooks. `full agent status` shows the
installed and shipped versions and anything the hooks would miss; `full agent
uninstall` reverses it. A directory-sourced marketplace from an earlier setup is
replaced. Restart sessions after installing or updating: a running session may
still hold older instructions. Installing the Python package inserts nothing
into any agent configuration; only this explicit command does.

Open the dashboard with `project-observatory full open` (local files) or
`project-observatory full open --serve` (loopback server, needed for the keys
page's live actions).

## Enable background or paid actions deliberately

Settings under `features` control scheduler, agent interpretation, embeddings,
notifications, retention, fixture cleanup, wiki projection, memory remediation
and private registry history. Their default is disabled. Configure model
selection and a budget before enabling reasoning or embeddings. On macOS,
`tools/install_launchd.py` and `tools/serverd.py` install workspace-specific
jobs only after explicit scheduler opt-in; Linux can run the CLI under a
supervisor chosen by the user. Do not create duplicate writers for one home.

A launchd job does not inherit your shell. The installer writes the directories
of the `PATH` it runs with (absolute, existing, not group- or world-writable)
followed by the system directories into the job, so tools such as `claude`,
`heroku` or `gh` resolve as they do in your terminal. After installing a tool
in a new directory, run `tools/install_launchd.py install` and
`tools/serverd.py --install` again.

## Upgrade, back up, restore

Stop every writer, including old executables and background jobs. A lock in a
new version cannot constrain an old process that does not know that lock.

```sh
project-observatory full upgrade
project-observatory full workspace-backup --writers-stopped
project-observatory full upgrade --apply --writers-stopped
project-observatory full doctor
```

The first command previews changes. Apply creates a private snapshot and
validates the staged upgrade. The original `full backup` command retains its
older database-only meaning; `workspace-backup` snapshots the whole managed
workspace. Keep the snapshot and matching previous application release.

To restore, select a new empty home with global `--home` and pass the private
snapshot directory to `full restore`. Never point old code at newer data to
simulate a downgrade. [COMPATIBILITY.md](COMPATIBILITY.md) specifies supported
formats, failure handling, backup exclusions and the tested migration matrix.

For an original installation whose state lived beside source, set a new home
and run `full migrate-local ORIGINAL_DIRECTORY` to preview. Apply requires
`--apply --writers-stopped`. It leaves the original in place and does not start
services. Verify external source paths, enabled features, credentials, registry
counts and database health before choosing which installation becomes active.
