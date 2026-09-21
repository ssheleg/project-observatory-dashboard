# Project Observatory metric plugins

A plugin contains a JSON manifest and a Python script in `plugins/`. Registering
a plugin requires no change to the metric readers or dashboard.

The manifest declares `id`, `title`, `script`, `metrics`, and `why`. Each metric declares
its name, unit and meaning. `api_version` is `1`; omitting it preserves the
legacy version 1 contract. Unsupported versions are refused before execution.
Script paths must remain inside the plugin directory, including after resolving
symlinks. A plugin is trusted local code: review it before enabling it.

No arguments, no stdin are passed to the script. Import `paths.DATA` for the
explicitly configured project source and `paths.REGISTRY` for the user's private
registry. Do not inline machine directories or assume credentials exist. The
`paths-current` validation convention checks source-path assumptions.

Requirements are checked before execution. `secret:NAME` resolves below the
configured `sources.secret_store` (or the workspace's `secrets/` directory),
`config:NAME` below private `config/`, and `registry:NAME` below private
`registry/`. These paths must be relative and cannot escape through `..` or a
symlink. `integration:KEY` requires the corresponding private settings flag to
be explicitly `true`. Cloudflare analytics uses `cloudflare_analytics`, GA4 uses
`ga4`, and Search Console uses `search_console`; direct script entry points also
check these flags. Existing `env:NAME`, `path:PATH`, `bin:NAME`, and `network`
requirements remain supported. `network` documents a need; it does not probe
connectivity or grant authorization. Missing requirements produce a recorded
skip before the script executes.

Write one JSON object per line to stdout (NDJSON). Every row carries
`project_id`, `metric`, `at` in UTC `YYYY-MM-DDTHH:MM:SSZ` format, numeric `value`,
and optional `payload`. Use declared metric names and existing project IDs.
The runner takes the unit from the manifest and rejects non-finite values.
Print a short, secret-free explanation of missing inputs or unmapped data to
stderr. A nonzero exit records a skipped plugin; do not manufacture zero
measurements for data that was never collected.

Use `python collectors/run_plugins.py --check` to validate manifests, then run
`python collectors/run_plugins.py` in an initialized private workspace. Provider
plugins need their own explicitly enabled integrations and private credentials.
Valid rows are upserted into the private
metrics database. Repeating an identical project/metric/time measurement replaces
that measurement rather than duplicating it. Failed plugins and refused rows are
recorded in the run receipt so callers can distinguish partial results from a
complete run. Never print credential values or raw authorization errors.
