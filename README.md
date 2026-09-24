# Ivan Soprun — interview portfolio

One static page for employment interviews (AI Automation / Applied AI / software). Four featured projects and three short mentions. No project is labeled PRODUCTION.

GitHub: [kot0070](https://github.com/kot0070).

## Open locally

From this directory:

```bash
python3 -m http.server 8080
```

Then open http://localhost:8080/

You can also open `index.html` directly. Styles, script, and the claim map use relative paths.

## GitHub Pages

The site is plain HTML, CSS, and JS at the repository root. No build step.

**Option A — GitHub Actions (preferred)**

1. In the repo: Settings → Pages → Build and deployment → Source: **GitHub Actions**.
2. `.github/workflows/pages.yml` runs on pushes to `main`.
3. It checks `public/claims-source.json` against `index.html`, then publishes the static files.

The project URL will look like `https://kot0070.github.io/portfolio/`.

**Option B — deploy from a branch**

1. Settings → Pages → Deploy from a branch.
2. Branch: `main`, folder: `/ (root)`.
3. `.nojekyll` is present so Jekyll does not rewrite the site.

## Claim map

`public/claims-source.json` lists every public sentence and the fact-lock fields behind it (`verified_purpose`, `maturity_label`, `do_not_claim`, and the other locked fields).

Presentation lines (order, “mention only”) are marked `backing: PORTFOLIO_SELECTION` and do not pretend to be metrics.

After editing copy in `index.html`:

```bash
python3 scripts/build_claims_source.py --write
python3 scripts/build_claims_source.py --check
```

Claims live on elements with `data-claim`. `data-fields` names the fact-lock fields. `data-polarity` marks denials, limitations, and caveats so a forbidden boast is not stored as an assertion.

## What this page will not say

- No PRODUCTION maturity.
- Bruno Electric does not work offline after first load. The service worker was retired.
- Bruno AC’s service-worker cache docs disagree with the runtime (`bruno-ac-v4` / `bruno-ac-v64` / `bruno-ac-v31`). That is a limitation.
- UAS Stage-1 is EARLY DEVELOPMENT and mention-only.
- The centerpiece repository [local-llm-benchmark](https://github.com/kot0070/local-llm-benchmark) is public on GitHub. The other six subject repositories named on the page remain private (Bruno apps are also proprietary). Bruno demos need redaction. This page does not publish proprietary catalogs, customer data, or release databases.
