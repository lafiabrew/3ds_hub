# 3DS Pages privacy, rendering and publication audit

Started 2026-11-03; catalogue integration authorized 2026-11-04. This is a **website/docs correction**, not application, hardware or release acceptance. The homepage remains the script-free FBI release catalogue; documentation lives alongside it under `/docs/`. Static Pages does not run the local SD-transfer or installer programs.

## Findings and corrections

| Finding | Correction / evidence boundary |
|---|---|
| Fixed deployment examples | Initial source inventory found nine identifying-address occurrences in SOP, cheatsheet and troubleshooting. Values are not repeated. Current guides use quoted placeholders or device-displayed addresses. Source/current rendered text is checked; history, caches, every source-code example and general privacy are not certified. |
| Raw Mermaid source | A pinned same-origin Mermaid 11.12.2 bundle is loaded only for diagram pages through Primer's hook. Original source remains accessible; failed library/diagram loads do not hide it. No Mermaid runtime CDN dependency. Other existing theme assets are a separate dependency. |
| Unreadable/invalid diagrams | Wide SVGs scroll. Strict settings are protected from diagram overrides; click callbacks are not bound. Bad syntax is isolated. Real Chromium tests cover visibility, source, small viewport, missing library, HTML-like labels, repeated loading and an omitted-loader counterfactual. No universal/legacy-browser claim. |
| Liquid inside code fences | Real Jekyll consumed an unprotected Go-format inspection template while only warning and exiting 0. Raw guards now preserve the actual rendered command. The official build helper rejects Liquid diagnostics; guard-removal mutation is rejected. Release-workflow schematic expressions are protected too. |
| Publisher changed during review | The new workflow initially uploaded only its generated catalogue, dropping SOP/architecture routes. Docs are built separately and composed through `site/docs-manifest.json`; Jekyll cannot overwrite the catalogue index, JSON, QR files or styling. |
| Unintended publication | Manifest-approved docs/specs HTML and four required assets are the only new output. Agent instructions, implementation plans, templates, tests, service/app code, captures and private logs are source-only. Unknown Markdown classification or missing STATUS blocks validation. |
| Partial or mixed artifact | Composition creates only a NEW output, never replacing inputs/existing output. Copies are checked; readiness is written last. Copy/signal/removal-failure tests preserve inputs and retain ownership on failed cleanup. Docs and catalogue must identify the same CI source SHA. Failed build/probe/browser steps cannot upload/deploy. |
| Stale safety assertions | Current guides distinguish private PKHX parsing, incomplete backup/native recovery, synthetic observations, fixed cheats and app-local stand-ins. Requirements/history are not completion evidence. These code defects are not repaired by prose. Root aggregate build failure propagation remains open. |
| Startup side effects | Inspection startup uses `--push ''`, overriding inherited `IP`; dashboard installation actions still require separate operator authorization. |

## Source audit

The initial hub source was `d3bae799fbe8f68d803c986981a09e945dd53412`; integration refreshed onto public `60269b3fd15e8d5099ed18f20a927443e4eb3ba7`. No unrelated local commits, app binaries, profile edits or task logs are part of the site patch. Source navigation uses GitHub URLs rather than nonexistent sibling folders on Pages. ParkShift remains local-only, with no public reviewed download or release asserted.

Primary public snapshots were fetched and matched the previously audited source files byte-for-byte:

| Project | Immutable primary source |
|---|---|
| PokeDash | [`6d0dc218bf`](https://github.com/lafiabrew/3ds_pokedash/blob/6d0dc218bf6fcc397c997ecdb373c82dfb45ab0d/src/pkhex.c) |
| Drop | [`d3b0dfd3ad`](https://github.com/lafiabrew/3ds_drop/blob/d3b0dfd3ad7c60d48b815d1264560fd5d007db28/src/drop_server.c) |
| WiGLE | [`0e5e3435f6`](https://github.com/lafiabrew/3ds_wigle/blob/0e5e3435f612fb049d03a8d946c606616aa66352/src/wigle.c) |
| PokeRNG | [`7e52b5c072`](https://github.com/lafiabrew/3ds_rngtool/blob/7e52b5c072e29f9ce0852dd6be9f209be472a446/src/rng_tool.c) |
| NetPass | [`a88247d300`](https://github.com/lafiabrew/3ds_netpass/blob/a88247d300c8ec5848c70d44259f7b798ec5001f/src/netpass.c) |
| Pokédex | [`694a58e1b0`](https://github.com/lafiabrew/3ds_pokedex/blob/694a58e1b0e0ec7368800eaa4f949f93ea3353ba/src/pokedex.c) |

[Current safety limits](../STATUS.md) explain what inspection establishes. It does not prove real-format edits, power-loss recovery, genuine radio/location data, per-game cheats, system coin/CECD integration, clean provisioning or console compatibility.

## Reproduce the composed-site gates

From the hub checkout on Linux with Python 3, Node/npm, Podman and a compatible installed Chromium, use **one standalone fail-fast entry point**. Replace the declared browser placeholder with your actual executable ([browser setup](https://playwright.dev/docs/browsers)):

```sh
CHROMIUM_EXECUTABLE=/path/to/chrome sh tests/pages/validate_composed.sh
```

The script owns a fresh workspace, logs each stage separately, preserves the first failing native status and does not launch later stages after failure. It runs source/privacy and composition regressions, pulls/builds the pinned Pages stack, builds a catalogue through the existing captured API transport, composes a NEW artifact, installs pinned Playwright Core outside the checkout, then runs browser and cancellation/cleanup gates. A PATH-stub success control, prerequisite-failure injection and deliberately error-swallowing canary test this exact script's control flow; those controls are offline evidence, not real runtime acceptance.

Source inventory includes current non-hidden historical/source-only Markdown without echoing identifying values. Loopback/listener/RFC 5737 controls pass and an identifying-host mutant must fail. Manifest classification is exhaustive; STATUS is never an implicit exception.

The fixture catalogue proves production builder/transport integration with captured metadata, not current live releases/binaries. CI builds from the live public API and retains independent QR/Range probes. Docs use github-pages 232/Jekyll 3.10.0/Primer with the observed project configuration; local default is rootless Podman and CI selects Docker with a non-root UID. No host Ruby is needed. CI may supply its ephemeral contents-read metadata token; output credential checks precede upload.

Browser gates serve actual generated/composed bytes, not an injected nominal hook. They check preserved catalogue bytes, all required routes/hashes, source-only exclusions, rendered privacy, literal inspection/workflow examples and every published diagram. Missing-STATUS, malformed-source, missing-library and omitted-loader controls must be rejected or degrade visibly as specified. Cleanup probes cover the exercised PID/listener paths, not every platform startup race. Old capture mode is a separate legacy-shape regression; captures may contain old addresses and must stay outside source.

## Deployment verification and remaining boundaries

Before main integration, push only the reviewed candidate branch and manually dispatch `gh workflow run pages.yml --repo lafiabrew/3ds_hub --ref REVIEWED_BRANCH` (replace the declared branch). The workflow's main-only automatic trigger is not a branch test. Bind the run to the reviewed SHA using `gh run list --repo lafiabrew/3ds_hub --workflow pages.yml --branch REVIEWED_BRANCH --commit FULL_COMMIT_SHA --json databaseId,headSha,status,conclusion`; wait for successful actual Ubuntu Docker/composition/browser gates and confirm deploy is skipped on that non-main ref. Do not push main if this stage fails. Refresh public main before a non-force integration; a new writer requires reconciliation and affected revalidation.

After an authorized main integration, the exact intended Pages workflow/deploy commit must succeed. With the exported browser environment, run `node tests/pages/test_pages.cjs --live-url https://lafiabrew.github.io/3ds_hub/ --expected-commit FULL_COMMIT_SHA` (replace the declared SHA), then `python3 tools/probe_pages.py --url https://lafiabrew.github.io/3ds_hub/ --minimum-installs 16`. A local/PR/build pass, HTTP 200 or old successful workflow is insufficient. `docs/publication.json` ties allowed paths and hashes to the catalogue source SHA. Inspect actual live SOP/architecture responses; do not treat deletion/404 as anonymized documentation restoration.

Unchanged source-only `AGENTS.md` corrections still require file-specific approval. Native unsafe implementations, sibling/current remote revisions, provisioning, physical/live-service evidence and app publication need their own work/authorization. Nothing here authorizes real installs, valuable-save edits, title deletion, generated-cheat activation or synthetic-observation upload. No history/cache erasure, universal privacy, dependency security audit or all-browser/device acceptance is claimed.
