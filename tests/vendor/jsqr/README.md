# Vendored jsQR (test/probe-only independent decoder)

- Upstream: https://github.com/cozmo/jsQR at commit `8e6a036beafa7053dd44b1b76ac578d22b1b3311`.
- Files: `dist/jsQR.js` copied unmodified as `jsQR.js`; upstream `LICENSE` copied unmodified.
- License: **Apache License 2.0** (see `LICENSE`). Upstream has no `NOTICE` file at this commit.
- Integrity: `PROVENANCE.json` records the upstream Git blob IDs and SHA-256 digests.
  `tools/probe_pages.py` refuses to run if either file's SHA-256 differs.

Why it is here: the hub's QR codes are produced by the hub's own encoder
(`serve_3ds.encode_qr_matrix` / `render_qr_svg`). Checking them with that same
code's inverse would prove nothing. `tools/probe_pages.py` and
`tests/test_catalog.py` instead rasterize the generated SVG files and decode the
pixels with this unrelated, pinned decoder running in Node.

It is never copied into the published Pages artifact, never installed through a
package manager, and is not an application asset.
