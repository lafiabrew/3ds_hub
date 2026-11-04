# Documentation index

The current guides describe local inspected behavior and its limits, not blanket release acceptance.

## Operator guides

- **[Current status and safety limits](STATUS.md)** — source-linked compatibility, backup, observation-provenance, system-integration and build-gate boundaries. Read first.
- [Setup and safe inspection](SOP.md) — prerequisites, command origins, per-app validation and explicitly withheld unsafe journeys.
- [Field reference](CHEATSHEET.md) — short commands and bounded controls, not firmware-repair instructions.
- [Troubleshooting](TROUBLESHOOTING.md) — preserve identity/data/evidence instead of guessing at deletion or recovery.

## Installation and release infrastructure

- [Install from the catalogue](INSTALL_FROM_HUB.md)
- [Release-kit contract and evidence](RELEASING.md)
- [Release rollout procedure](RELEASE_ROLLOUT.md)

## Maintainer references

- [Architecture](ARCHITECTURE.md) — actual component and evidence boundaries.
- [Accuracy playbook](AGENT_PLAYBOOK.md) — source/command/device proof, isolation and review.
- [Constitution](../specs/CONSTITUTION.md) — required invariants, not proof every implementation conforms.
- [Canonical terms](../specs/CONTEXT.md) — distinguish private PKHX, native formats, IDs and replacement guarantees.
- [Suite requirements](../specs/01-3ds-homebrew-suite.md) — intended behavior, explicitly not a completion report.
- [Historical audits](audit/README.md) — dated evidence whose earlier assurances are not current operating instructions.

The [repository README](https://github.com/lafiabrew/3ds_hub/blob/main/README.md) lists build-metadata inventory. The [site homepage](https://lafiabrew.github.io/3ds_hub/) remains the release catalogue, not a Jekyll copy of that README. Separate app READMEs and the organization profile have independent histories and may still need corrections; existing `AGENTS.md` updates require explicit file-specific approval. No current guide certifies real-save editing, physical recovery, live WiGLE eligibility or all-console compatibility.
