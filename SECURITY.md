# Security and privacy boundary

Project Observatory portable edition observes explicitly selected local projects. It is not a credential isolation boundary against the same operating-system user, malware, an untrusted child process or a privileged administrator. The implementation is in [`observatory/`](observatory/); synthetic security tests live in [`tests/test_observatory.py`](tests/test_observatory.py).

## What stays private

The state directory is outside source by default. It contains configured absolute paths, project metadata, names and equality fingerprints, local history and optional plaintext secret slots. POSIX directories use mode 700 and files use mode 600; secret reads reject wider permissions. No claim of encrypted-at-rest storage is made. Use OS disk encryption and an appropriately secured account.

Environment values are read transiently for HMAC equality fingerprints. The salt is random per installation and stays local. Fingerprints are still sensitive equality metadata and are omitted from aggregate exports. Snapshots retain the most recent 100 observations. No automatic external backup or retention erasure guarantee is provided.

Never publish runtime config, SQLite files, generated dashboards, credential slots, transcripts or real screenshots. Never copy the private predecessor's Git history or inventory into this distribution. `site/` is the public static artifact; runtime state is not a deployment input.

## Input and output controls

- Secret input is a hidden local prompt or stdin. No secret-value argument exists.
- Secret listing returns names only. Child-process injection suppresses stdout/stderr; the child is not sandboxed.
- Known-value findings contain slot names, opaque target identifiers and counts. They contain no raw matching value or snippet.
- General OS failures omit exception details that might reveal sensitive filenames. CLI `status` and project listings still deliberately contain private metadata; keep their output local.
- Project discovery previews scope without enrolling it. No provider calls, remote fetch, model spend, auto-scheduler, desktop notifications or third-party memory writes occur.
- Project traversal ignores symlinked files/directories and common dependency/build directories. State writes reject symlinks. These checks are not a defense against a malicious same-user process racing filesystem changes.

## Local dashboard

The server binds only `127.0.0.1`. Exact Host/Origin checks reject DNS-rebinding hostnames and prefix lookalikes. It serves one read-only route with no-store, a restrictive Content Security Policy, no scripts, and no credential reveal/provisioning routes. HTML data is escaped. This is an unauthenticated local view accessible to processes/users able to reach that loopback port; do not proxy it onto a public network or use it on an untrusted shared host.

## Detection limits

Known-value matching detects only exact byte copies of explicitly stored slots. Unknown, encoded, transformed, split, short or rotated-away values are outside that evidence. Bounded input sizes, unreadable files and missing sources are reported as partial/degraded. A zero-match result is not a clean bill of health. Several named slots may share one value; occurrences per slot are not counts of unique credentials or incidents.

Local exposure in a transcript or memory database establishes that a value reached that artifact. It does not establish remote exfiltration, a vendor breach or an upstream product vulnerability. Demo data is fictional.

## Reporting an issue

Use the repository's private vulnerability-reporting channel if available. Otherwise contact the maintainer through the contact route on [sshlg.me](https://sshlg.me/) before sharing sensitive details. A public issue may describe the class and a synthetic reproduction. Never attach a real token, inventory, log, private path or customer identifier. Do not test a live credential or other users' data to prove a report.

## Release check

Before publication, inspect the complete prospective Git tree and archive, including docs, fixtures, comments and the site. Token-shape scanning alone cannot detect private project names or relationships. Run synthetic tests from a fresh checkout with empty HOME/state and inspect supported Python versions. A clean new repository is required; deleting private data from a tip commit does not remove it from history.
