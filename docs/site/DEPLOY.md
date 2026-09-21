# Public website deployment

The deployment input is the nine files in `site/`, checked by [`check.py`](check.py). This directory is separate from the application's private generated dashboard. Never deploy an Observatory home, repository root, database or generated dashboard.

## Validate and preview

```sh
python3 docs/site/check.py --self-test
python3 -m http.server 8766 --bind 127.0.0.1 --directory site
```

The self-test proves that an unexpected file, a private-path marker and mismatched case-study arithmetic are rejected. It supplements the complete source/history privacy gate in [`../../tools/check_public_release.py`](../../tools/check_public_release.py).

## Cloudflare Pages

The public project is `project-observatory`, with production branch `main` and custom domain <https://observatory.sshlg.me/>. The fallback host is <https://project-observatory.pages.dev/>. Use the maintainer's already-authorized Cloudflare login or a scoped credential held outside the repository. A fork must select its own account, project and domain and update the canonical URL, sitemap and robots file.

```sh
python3 docs/site/check.py --self-test
npx --yes wrangler@4.135.0 pages deploy site --project-name project-observatory --branch main
```

Select the account through Wrangler's supported login/account configuration. No token belongs in this command, a source file, chat, or Git history. The custom domain must be attached in Pages and its CNAME point to the project's Pages host. Domain setup is separate from deployment and may take time to validate TLS.

After deployment, compare the served HTML with `site/index.html`, inspect response headers and confirm the production/custom host in a browser. Check the onboarding, example toggle, keyboard copy path and mobile layout. Record the source revision and deployment identifier in the release handoff. The site makes no request to a running local Observatory and includes no analytics or external assets.

## Browser review on 2026-09-21

The same content was rendered in dawn and paper-led variants at 1440×900. Dawn was selected for separation of the introduction from the paper evidence sections. At 390×844, the installation command wrapped without document overflow (document and viewport both 390px). The synthetic toggle displayed the redacted finding, and the copy control produced its success state. Missing-JavaScript content remains present in the original HTML, including both example states. No claim of a complete WCAG conformance audit is made.

Wrangler may create a local `.wrangler/` cache. It is ignored by Git and is not a release input. Run source publication checks from a clean checkout; the release gate deliberately rejects runtime cache files that remain in the prospective public tree.
