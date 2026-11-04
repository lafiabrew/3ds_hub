# Canonical terms

Definitions describe contracts, not feature completion. See [current status](../docs/STATUS.md) for demonstrated boundaries.

| Term | Definition / boundary |
|---|---|
| **PKHaX / PokeDash** | Project terminology for permissive Pokémon editing experiments and calculators. The name is not proof of native-save or arbitrary ROM-hack support. |
| **PKHX block** | This implementation's private 512-byte block at file offset `0x1400`, identified by magic `0x58484B50`. Python requires it; the native loader has a synthesized fallback. It must not be conflated with a genuine generation-specific Pokémon save layout. |
| **Generation-specific checksums** | Actual format/version block descriptors, integrity fields and algorithms. Writing a fixed footer or checking the PKHX block does not establish genuine native-save validity. |
| **LayeredFS mod** | A title-specific Luma replacement directory under `luma/titles/<full-TitleID>/`; this workspace's toggler moves directories to/from `luma/titles_disabled/`. This definition does not certify safe recovery or target identity. |
| **Diagnostic bundle** | Whatever files/report the inspected server/scanner actually exposes and retrieves. Existence of a report does not imply complete logs, complete transfers or correct binary-dump interpretation. |
| **Temporary-file replacement** | Write candidate bytes to a temporary path and attempt a rename. This pattern alone is not checked backups, native atomic overwrite or physical power-loss recovery. The constitution states required guarantees separately. |
| **UniqueId** | Build-metadata allocation in `meta/app.rsf`: current catalog `0x0D3E0`–`0x0D3EF`; separate ParkShift candidate `0x0D400`. The old `0x0D3D*` range is historical, not allocation or deletion authority. A UniqueId is not a full installed TitleID; verify actual package identity. |
| **Discovered package** | An existing CIA/3DSX artifact found by the hub, potentially stale or outside root build membership. It is not necessarily a release or a validated current-source build. |
| **Hardware-verified** | Evidence recorded for an exact artifact, console model/CFW and tested journey. Host tests and native compilation do not establish this status. |
