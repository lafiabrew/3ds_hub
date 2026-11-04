#!/usr/bin/env python3
"""Compose a NEW docs+catalogue artifact without mutating either input.

Existing output is always refused. Copy failures/interruption never expose a
ready manifest; failed removal retains an explicit ownership receipt. GitHub
Pages deployment happens only after later probes and workflow gates succeed.
"""
from __future__ import annotations
import argparse
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import signal
import sys

from pages_docs import ROOT, findings, load_manifest, safe_relative

READY = "docs/publication.json"
CATALOG_FILES = {"index.html", "catalog.json", "style.css", "favicon.svg", ".catalog-build.json"}
QR_PATH = re.compile(r"qr/[A-Za-z0-9_.-]+\.svg\Z")
SHA = re.compile(r"[0-9a-f]{40}\Z")


class Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)


def real_file(directory: Path, relative: str) -> Path:
    safe_relative(relative)
    candidate = directory / relative
    # Reject every symlink ancestor, even a link that currently points inside.
    current = directory
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("symlinked publication input")
    if not candidate.is_file() or not candidate.resolve().is_relative_to(directory.resolve()):
        raise ValueError("required publication input missing or outside its root: " + relative)
    return candidate


def catalogue_files(catalogue: Path, base: str) -> tuple[dict, list[str]]:
    catalog = json.loads(real_file(catalogue, "catalog.json").read_text())
    if catalog.get("base_path") != base or not isinstance(catalog.get("apps"), list):
        raise ValueError("catalogue base path/schema mismatch")
    paths = set(CATALOG_FILES)
    for app in catalog["apps"]:
        if app.get("install"):
            qr = app["install"].get("qr_svg", "")
            if not isinstance(qr, str) or not QR_PATH.fullmatch(qr):
                raise ValueError("unsafe catalogue QR path")
            paths.add(qr)
    for name in paths:
        real_file(catalogue, name)
    actual = set()
    for path in catalogue.rglob("*"):
        if path.is_symlink():
            raise ValueError("symlink in catalogue input")
        if path.is_file():
            actual.add(path.relative_to(catalogue).as_posix())
    if actual != paths:
        raise ValueError("catalogue contains unexpected or missing publication files")
    # The hidden local-build ownership marker was never part of the deployed catalogue.
    return catalog, sorted(name for name in paths if not name.startswith("."))


def compose(catalogue: Path, docs: Path, output: Path, *, root: Path = ROOT) -> dict:
    if catalogue.is_symlink() or docs.is_symlink():
        raise ValueError("symlinked publication root")
    catalogue, docs, output = catalogue.resolve(), docs.resolve(), output.absolute()
    if output.is_symlink() or output.exists():
        raise ValueError("output already exists; choose a NEW directory")
    resolved = output.resolve()
    if resolved in (Path("/"), Path.home().resolve()) or any(
            resolved == p or resolved in p.parents or resolved.is_relative_to(p)
            for p in (root.resolve(), catalogue, docs)):
        raise ValueError("output must be separate from source and inputs")
    manifest = load_manifest(root)
    catalog, catalog_paths = catalogue_files(catalogue, manifest["base_path"])
    if set(catalog_paths) & set(manifest["outputs"] + [READY]):
        raise ValueError("catalogue/docs path collision")
    token_values = [os.environ.get(name, "").encode() for name in ("GITHUB_TOKEN", "JEKYLL_GITHUB_TOKEN")]
    tokens = [value for value in token_values if value]
    inputs = {name: real_file(catalogue, name) for name in catalog_paths}
    for name in manifest["outputs"]:
        inputs[name] = real_file(docs, name)
    digests = {}
    for name, source in inputs.items():
        data = source.read_bytes()
        if any(token in data for token in tokens):
            raise ValueError("credential material found in publication input")
        if name.endswith(".html"):
            parser = Text(); parser.feed(data.decode("utf-8"))
            if findings("".join(parser.parts)):
                raise ValueError("identifying host literal in HTML: " + name)
        digests[name] = hashlib.sha256(data).hexdigest()
    ci_sha = os.environ.get("GITHUB_SHA", "")
    if ci_sha and not SHA.fullmatch(ci_sha):
        raise ValueError("invalid publication source SHA")
    if catalog.get("hub_source_sha") != (ci_sha or None):
        raise ValueError("docs/catalogue source SHA mismatch")
    publication = {"schema": "3ds-docs-publication-v1", "base_path": manifest["base_path"],
                   "hub_source_sha": ci_sha or None, "pages": manifest["pages"],
                   "assets": manifest["assets"], "source_only": manifest["source_only"],
                   "sha256": {name: digests[name] for name in manifest["outputs"]},
                   "catalogue_sha256": {name: digests[name] for name in catalog_paths}}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir()  # Exclusive ownership; a concurrent writer causes a loud failure.
    print("Owned incomplete publication directory: " + str(output), file=sys.stderr, flush=True)
    try:
        for name, source in inputs.items():
            dest = output / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
            if hashlib.sha256(dest.read_bytes()).hexdigest() != digests[name]:
                raise ValueError("publication copy digest mismatch")
        # Readiness is emitted LAST, after every allowlisted byte has been checked.
        ready = output / READY
        with ready.open("x", encoding="utf-8") as handle:
            json.dump(publication, handle, indent=2, sort_keys=True)
            handle.write("\n")
        return publication
    except BaseException:
        try:
            (output / READY).unlink(missing_ok=True)
            shutil.rmtree(output)
        except BaseException:
            print("Cleanup incomplete; RETAINED owned directory (do not upload): " + str(output), file=sys.stderr, flush=True)
        raise


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", type=Path, required=True)
    p.add_argument("--docs", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    def interrupted(_signal, _frame):
        raise InterruptedError("publication interrupted")
    signal.signal(signal.SIGTERM, interrupted)
    try:
        publication = compose(args.catalog, args.docs, args.output)
    except (OSError, ValueError, KeyError, TypeError, KeyboardInterrupt) as error:
        print("Composition failed; existing inputs/output untouched: " + type(error).__name__, file=sys.stderr)
        return 1
    print(json.dumps({"pass": True, "pages": len(publication["pages"]), "assets": len(publication["assets"]),
                      "source_sha": publication["hub_source_sha"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
