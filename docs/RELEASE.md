# Portable 0.1.0 release verification — 2026-09-21

This receipt describes measured local checks, not a promise that every vulnerability or private fact is detectable. Publication and deployment are separate actions, recorded by the release owner after the final combined source/site commit.

## Reviewed source

Source root: [`1248e02d0c25df3700693e8c8459c856d57329d2`](https://github.com/ssheleg/project-observatory-open-source/tree/1248e02d0c25df3700693e8c8459c856d57329d2). It contains 20 public source/documentation/test files and a new Git root. Author and committer use generic project contributor metadata. No private repository history was imported.

| Runtime file | Reviewed SHA-256 |
|---|---|
| `observatory/core.py` | `55dc9d60df02013adc048835c35d22771db895e0edd71fc844ee09a81f181fd4` |
| `observatory/credentials.py` | `cbe361e4276555acb08b7eb210b8ce50bd8004a24a6fc4d45c626f8ac36286c5` |
| `observatory/dashboard.py` | `d0243461b8493e45a4d94f2824b5e8e1e5ec40a76c9c5300ad7bad5d1c202bea` |
| `observatory/cli.py` | `eae6a4a3a5586ac805bc5184c3fbbe06cb028a5246654efb5f16a0b470386098` |

An independent agent reproduced and checked the runtime boundaries. The review identified Git clean-filter execution during status, a replaced-root symlink escape, known values echoed through metadata labels, unbounded generated SQLite payloads, and malformed snapshot fields. Each was fixed and covered by a runtime regression before this receipt. No remaining P0/P1 was identified within the reviewed scope. That is a bounded review conclusion, not a security certification.

## Checks actually run

| Check | Result and practical limit |
|---|---|
| `python3 -W error::ResourceWarning -m unittest discover -s tests -q` from a fresh local clone | **27 tests, OK**, Python 3.14.7; synthetic roots and local Git remote, no provider account |
| Independent runtime rerun | **27 tests, OK**, with ResourceWarning treated as an error; reviewed runtime hashes unchanged except a doctor-description correction independently verified as text-only |
| Fresh virtual environment, `python -m pip install .` | Built and installed the package; runtime has no third-party dependency requirement |
| Installed `demo`, `doctor`, `export` | Passed; one fictional project, two synthetic known-value occurrences, one named exposure finding; export omitted identifiers |
| `python tools/check_public_release.py --history` | Source/tree/path/blob checks passed; release owner repeats on combined site/source history |
| Same checker with a local private-identifier denylist | Passed against 302 curated identifiers; raw denylist and private audit stay outside the public repository; exact-boundary matches avoid public-name prefix collisions |
| `python docs/site/check.py --self-test` | Passed 9 static files and negative probes for unexpected file, private marker and aggregate mismatch |
| Parent browser walkthrough of actual synthetic localhost runtime | Reviewed 390×844 and 1440×900; document width matched narrow viewport, table scrolled internally, no browser errors; one fictional project/finding and exposure summary visible |

The checker also has synthetic negative tests for token shapes, private identifiers, runtime folders, tracked build/cache files and disallowed paths deleted from the current tree but still present in history. Matched values are never printed. Human review remains required for contextual private facts and identifiers absent from a denylist.

## Package archive

Independently inspected wheel: `project_observatory-0.1.0-py3-none-any.whl`.

SHA-256: `4f161eb2d6365ff5351302da70437177648b2e3345da8dda4d4afe4bb7a44183`.

The inspected archive contains 12 entries: six `observatory` source modules and six distribution/license metadata entries. Source bytes match the reviewed runtime. There are no absolute paths, traversal or symlink entries; every member passed the public pattern scan. No operational state, history, site or private documentation is bundled. The metadata declares Python 3.11+ and a generic author. The hash identifies this inspected artifact; a later wheel build may have different ZIP timestamps and must be checked separately.

## Remaining release and development boundaries

The release owner must verify the final combined commit, public remote HEAD, repository visibility and deployed static artifact. The GitHub CI matrix separately exercises Python 3.11 and 3.14 on Linux and 3.14 on macOS; local success does not claim those remote jobs already ran. Windows has not been validated.

Future provider/MCP/scheduler/admin work remains in [MIGRATION.md](MIGRATION.md); UI work is broken into scenario-driven packets in [UI-PLAN.md](ux/UI-PLAN.md). The private predecessor remains a separate operational system and must not be made public as a substitute for this distribution.

## Observed publication

The public `v0.1.0` tag resolves to [`d2ac94082a31b64a95482dc6b97727b119955d1c`](https://github.com/ssheleg/project-observatory-open-source/tree/d2ac94082a31b64a95482dc6b97727b119955d1c). GitHub reports the new repository PUBLIC; its initial remote `main` matched that revision. Private vulnerability reporting is enabled. The original operational repository was not made public.

The final pre-publication gate inspected **36 files and 38 historical blobs**, including the static site, against the local **302-identifier** denylist: passed, no findings. Git authors/committers were inspected separately and use generic project contributor metadata. The annotated release tag contains only the product/version description.

A fresh clone over the public HTTPS URL passed the history gate, static self-tests and **27 runtime tests**. [CI run 35586799064](https://github.com/ssheleg/project-observatory-open-source/actions/runs/35586799064) passed all three jobs: Python 3.11 on Linux, Python 3.14 on Linux, and Python 3.14 on macOS. No Windows claim is added.

Cloudflare Pages production deployment `8e675a83-d974-4e11-86cb-cafd9df48183` reports `success` and source commit `d2ac94082a31b64a95482dc6b97727b119955d1c`; the custom domain reports `active`. Both <https://observatory.sshlg.me/> and <https://project-observatory.pages.dev/> returned the exact reviewed `site/index.html` through curl. HTML SHA-256: `47bdd990ec26ac5d18af7f3b88aa6d61296450b6fe1341a53cb6738f5d8fa188`. The custom host returned HTTP 200 with the declared CSP, frame, content-type and permissions headers. The live page also rendered its explanation, historical count boundary and Python 3.11 onboarding in the browser. Python urllib requests returned 403; browser and curl access succeeded, so universal client compatibility is not claimed.

Only the eight public assets plus `_headers` were uploaded. No local dashboard or state was deployed. Existing authorized credentials were supplied locally to the deployment client and are not part of this repository or receipt. See [deployment instructions](site/DEPLOY.md) for repeatable validation and publication.
