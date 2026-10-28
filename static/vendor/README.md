# Vendored front-end libraries

Served from this folder; never loaded from a CDN (SECURITY.md). Approved by the user on 2026-10-27 (Pico CSS on 2026-10-28).

| Library | Version | File | SHA-256 | Source |
|---|---|---|---|---|
| HTMX | 2.0.11 | `htmx/htmx-2.0.11.min.js` | `d6fdc75f204e6bdefa99b69bf1e6d4ac69b8a364f77929f45c13476b4000f717` | npm `htmx.org@2.0.11`, `dist/htmx.min.js` (BSD Zero Clause, see `htmx/LICENSE`) |
| Chart.js | 4.5.1 | `chartjs/chart-4.5.1.umd.min.js` | `48444a82d4edcb5bec0f1965faacdde18d9c17db3063d042abada2f705c9f54a` | npm `chart.js@4.5.1`, `dist/chart.umd.min.js` (MIT, see `chartjs/LICENSE.md`) |
| Pico CSS | 2.1.1 | `pico/pico-2.1.1.min.css` | `fbc9a63fc9fc9f72d12fd7fc9806e11fa9f77ae4f9cad146b27003a1119ba3db` | npm `@picocss/pico@2.1.1`, `css/pico.min.css` (MIT, see `pico/LICENSE.md`) |

Pico's form icons are `data:` URIs, which the CSP blocks. They were decoded from the light theme in `css/pico.css` into `pico/icons/*.svg`, and `static/css/portal.css` points the `--pico-icon-*` variables at those files.

Each npm tarball was checked against the registry's published `sha512` integrity value before extracting.

To upgrade: download the new tarball from `https://registry.npmjs.org/<name>/-/<name>-<version>.tgz`, check its integrity value, copy the file with the version in its name, update the template that loads it and this table.
