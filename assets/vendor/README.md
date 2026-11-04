# Vendored Mermaid renderer

- Package: `mermaid` **11.12.2**, single `dist/mermaid.min.js` browser bundle.
- Upstream: <https://github.com/mermaid-js/mermaid>, npm distribution `https://registry.npmjs.org/mermaid/-/mermaid-11.12.2.tgz`.
- Tarball integrity verified against registry metadata: `sha512-n34QPDPEKmaeCG4WDMGy0OT6PSyxKCfy2pJgShP+Qow2KLrvWjclwbc3yXfSIf4BanqWEhQEpngWwNp/XhZt6w==`.
- Browser SRI: `sha384-1ggI9FC3CkghppRD/XCR4aD+jp4DxwXlJIW0wxhyTLNKuiZEW3c4BwcjKXl0iVAJ`.
- License: [MIT license text](MERMAID-LICENSE), retained without modification.

The Primer `head-custom.html` hook loads the small local adapter. The bundle is fetched from the same Pages origin **only when a page contains a Mermaid block**; it does not depend on a public CDN at runtime. Raw Markdown fences remain compatible with GitHub's native rendering.

The adapter initializes strict security, does not bind source click handlers, preserves original source under a disclosure after successful rendering, and leaves source visible with a notice if the renderer or diagram fails. Each diagram is handled independently. Wide SVGs scroll instead of being squeezed into unreadable text.

To update: select an explicit package version, verify its tarball integrity and license, replace the bundle/versioned filename, regenerate the SHA384 SRI in the include, and rerun browser/privacy tests and independent review. An image or bundle hash identifies bytes; it is not an independent security audit of the dependency.
