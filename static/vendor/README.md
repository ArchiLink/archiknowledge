# Vendored front-end libraries

Served from this folder; never loaded from a CDN (SECURITY.md). Approved by the user on 2026-10-27.

| Library | Version | File | SHA-256 | Source |
|---|---|---|---|---|
| HTMX | 2.0.11 | `htmx/htmx-2.0.11.min.js` | `d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717` | npm `htmx.org@2.0.11`, `dist/htmx.min.js` (BSD Zero Clause, see `htmx/LICENSE`) |
| Chart.js | 4.5.1 | `chartjs/chart-4.5.1.umd.min.js` | `48444a82d4edcb5bec0f1965faacdde18d9c17db3063d042abada2f705c9f54a` | npm `chart.js@4.5.1`, `dist/chart.umd.min.js` (MIT, see `chartjs/LICENSE.md`) |

Each npm tarball was checked against the registry's published `sha512` integrity value before extracting.

To upgrade: download the new tarball from `https://registry.npmjs.org/<name>/-/<name>-<version>.tgz`, check its integrity value, copy the file with the version in its name, update the template that loads it and this table.
