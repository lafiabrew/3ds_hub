# 3DS Pages privacy, rendering and accuracy audit — 2026-11-03

Scope: the public 3DS documentation site, its source Markdown, actual served HTML shapes and the documented implementation boundaries. This is **not application, console or release acceptance**. The site is static documentation; LAN transfer/installation still requires the separate local hub/console programs.

## Findings and corrections

| Finding | Evidence / correction | Remaining boundary |
|---|---|---|
| Fixed deployment examples | Initial source inventory found nine identifying-address occurrences across SOP, cheatsheet and troubleshooting. Values are not repeated in this report. Current guides use quoted placeholders or tool-displayed addresses. | This changes current documentation, not old Git history, existing browser/CDN caches, every source-code example or all possible identifiers. |
| Raw Mermaid source on Pages | Served home/architecture/playbook HTML contained Mermaid fences without a renderer. Primer's `head-custom.html` hook installs a small conditional adapter; actual Jekyll output includes its prefixed assets. | Deployed responses still require separate post-publication verification. |
| Renderer availability | Mermaid 11.12.2 is pinned, integrity-checked and served from this site only when needed. No runtime Mermaid CDN dependency. | It is a third-party dependency, not an independently audited codebase; the existing theme may have unrelated external assets. |
| Liquid inside code fences | Actual Jekyll 3.10 consumed the unprotected Go-format inspection template while only emitting a warning. Raw-block protection now preserves the exact rendered command, which was executed successfully. | Build exit 0 alone is insufficient; rendered-command and warning checks are required. |
| Bad/blocked diagrams | Strict initialization, protected security settings, independent per-diagram handling and preserved original source. Wide SVGs scroll rather than squash. | Modern Chromium integration was tested; universal/legacy-browser compatibility is not claimed. |
| Stale safety/capability claims | Current guides distinguish private PKHX parsing, incomplete backup/native recovery, synthetic observations, fixed cheat templates and app-local coin/text data. Requirements/history are not completion evidence. | Those implementation defects are not repaired by prose. Root aggregate build failures can still be concealed. |
| Local/deployed confusion | Public source links point to GitHub snapshots instead of nonexistent sibling directories on Pages. ParkShift remains local-only, without a public repository/download/validation guarantee. | No unpublished app files, binaries, task logs or profile changes are part of this site patch. |
| Startup side effects | Inspection startup examples explicitly pass `--push ''`, overriding an inherited `IP` target. | Dashboard installation controls still require operator authorization; the static Pages site does not run the LAN installer. |

## Source audit

The hub's public source snapshot was `d3bae799fbe8f68d803c986981a09e945dd53412` when this correction was prepared. Its `Makefile`, PC parser, server and constitution matched the previously inspected local versions. The following **public immutable implementation snapshots** were fetched and matched the primary audited files byte-for-byte:

| Project | Snapshot / primary source |
|---|---|
| PokeDash | [`6d0dc218bf`](https://github.com/lafiabrew/3ds_pokedash/blob/6d0dc218bf6fcc397c997ecdb373c82dfb45ab0d/src/pkhex.c) |
| Drop | [`d3b0dfd3ad`](https://github.com/lafiabrew/3ds_drop/blob/d3b0dfd3ad7c60d48b815d1264560fd5d007db28/src/drop_server.c) |
| WiGLE | [`0e5e3435f6`](https://github.com/lafiabrew/3ds_wigle/blob/0e5e3435f612fb049d03a8d946c606616aa66352/src/wigle.c) |
| PokeRNG | [`7e52b5c072`](https://github.com/lafiabrew/3ds_rngtool/blob/7e52b5c072e29f9ce0852dd6be9f209be472a446/src/rng_tool.c) |
| NetPass | [`a88247d300`](https://github.com/lafiabrew/3ds_netpass/blob/a88247d300c8ec5848c70d44259f7b798ec5001f/src/netpass.c) |
| Pokédex | [`694a58e1b0`](https://github.com/lafiabrew/3ds_pokedex/blob/694a58e1b0e0ec7368800eaa4f949f93ea3353ba/src/pokedex.c) |

See [STATUS](../STATUS.md) for what those observations establish. They do not prove genuine-format saves, native power-loss recovery, real radio/location provenance, per-game cheats, system coin/CECD integration, clean provisioning or physical-device behavior.

## Reproduction

Run from the hub checkout:

```sh
python3 tests/pages/check_privacy.py
```

This inventories tracked/new non-hidden Markdown, including historical docs; holdout content is excluded. It rejects identifying IPv4 literals without echoing their values and exercises an identifying-host mutant plus loopback/listener/documentation-range controls. It does not erase historical disclosures or certify general privacy.

For browser integration, use Node/npm and install the pinned SDK outside the checkout:

```sh
npm install --prefix /tmp/3ds-pages-tools --no-save --ignore-scripts --no-audit --no-fund playwright-core@1.58.2
```

Use a separately installed compatible Chromium executable; [browser setup documentation](https://playwright.dev/docs/browsers) describes installation options. Playwright Core does not download a browser in the command above. This update reused an existing cached Chromium and does not certify every browser/SDK combination. Capture real production HTML/theme resources **outside the repository**, because pre-fix captures can contain old identifying examples:

```sh
python3 tests/pages/capture_pages.py --out /tmp/3ds-pages-captures
```

Set the declared browser path to your actual executable. Run these exports and the following browser commands in the **same shell**; repeat the exports in each new terminal. Do not copy captures into the public checkout:

```sh
export PLAYWRIGHT_MODULE_PATH=/tmp/3ds-pages-tools/node_modules/playwright-core &&
export CHROMIUM_EXECUTABLE=/path/to/chrome &&
export PAGES_CAPTURE_DIR=/tmp/3ds-pages-captures &&
node tests/pages/test_pages.cjs
```

This first local gate uses actual captured production DOM and the candidate hook/assets. It checks SVG visibility, retained source, a small viewport, malformed-diagram isolation, strict HTML-like labels, missing-library fallback, repeated enhancement and the omitted-renderer counterfactual. Candidate diagram definitions are also rendered. Existing theme-script bytes are fulfilled from the real capture, not a fake implementation. This adapter test alone is **not a Jekyll build or live-site acceptance**.

A separate real build uses GitHub's official pinned Pages image (github-pages 232, Jekyll 3.10.0 and Primer), with the observed project URL/base path. No host Ruby or GitHub credentials are required. Choose a new empty output directory outside the checkout:

```sh
podman pull ghcr.io/actions/jekyll-build-pages@sha256:6791ebfd912185ed59bfb5fb102664fa872496b79f87ff8b9cfba292a7345041 &&
sh tests/pages/build_pages.sh /tmp/3ds-pages-site
```

Using the same browser environment, run `node tests/pages/test_pages.cjs --site-dir /tmp/3ds-pages-site`. This serves the actual generated HTML/assets without injecting the nominal hook, checks the rendered privacy inventory and diagram output, and asserts that Liquid preserved the documented inspection template. The candidate passed both build and browser gates. The standalone SDK defaults differ from the managed site's URL metadata, so the helper explicitly supplies the observed `/3ds_hub` configuration. A build/HTML/browser pass is still **not a deployed-site pass**.

Use the same environment with `node tests/pages/test_pages.cjs --cleanup-probe` to exercise cancellation and an injected graceful-close failure. Owned browser/listener resources must be confirmed closed; failed cleanup retains ownership evidence instead of silently passing.

After an authorized publication, use the same environment with:

```sh
node tests/pages/test_pages.cjs --live-url https://lafiabrew.github.io/3ds_hub/
```

Also confirm the Pages build reports `built`, no error and the intended public commit. A local/PR pass, HTTP 200 or unchanged old page is insufficient. Every inventoried public route, including the authoritative STATUS page, must return 200. The reviewed source-only exception list is currently empty; any intentional future exception must be explicitly reviewed, not silently inferred from a 404. Current source privacy and local rendering checks do not themselves prove the URL has updated.

## Remaining actions

- **Operator action:** explicitly authorize any protected root/app `AGENTS.md` corrections; they were not edited by this patch. Their older feature descriptions are not verification evidence.
- **Agent action, separately scoped:** repair root aggregate failure propagation and the unsafe/incomplete implementations, with real regressions and independent review. This patch changes no app or service behavior.
- **Operator action:** separately approve publication, installs/releases and physical/live-service tests where not already authorized. No games, binaries, private logs, profile edits or other local commits should be pushed incidentally.
- **Historical boundary:** old root plans/audits and sibling documents remain point-in-time records, not blanket current acceptance. Retain their limits and source/revision context.
