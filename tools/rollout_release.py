#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SEMVER_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
OWNED_PATHS = (
    ".github/workflows/homebrew-release.yml",
    ".github/homebrew-release.json",
    "docs/RELEASING.md",
)
EXTRA_ENGINE_REPOS = {"3ds_pockettracker", "3ds_neverball", "3ds_tuxpuck", "3ds_supaplex"}


class RolloutError(RuntimeError):
    pass


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - exact message propagated
        raise RolloutError(f"failed to read JSON {path}: {exc}") from exc


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _require_kit_ref(kit_ref: str) -> None:
    if not SHA40_RE.match(kit_ref):
        raise RolloutError("--kit-ref must be a full 40-char lowercase hex commit SHA")


def _row_map(rows: list[dict[str, Any]], key: str = "repo") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        repo = row.get(key)
        if not isinstance(repo, str) or not repo:
            raise RolloutError(f"row missing non-empty {key}")
        if repo in out:
            raise RolloutError(f"duplicate {key}: {repo}")
        out[repo] = row
    return out


def _validate_inputs(
    audit: dict[str, Any],
    profiles: dict[str, Any],
    readiness: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    audit_rows = audit.get("rows")
    profile_rows = profiles.get("rows")
    readiness_rows = readiness.get("rows")
    if readiness_rows is None:
        readiness_rows = readiness.get("public_repositories")
    if not isinstance(audit_rows, list) or not isinstance(profile_rows, list) or not isinstance(readiness_rows, list):
        raise RolloutError("audit/profiles/readiness rows must all be lists")

    audit_map = _row_map(audit_rows)
    profile_map = _row_map(profile_rows)
    readiness_map = _row_map(readiness_rows)

    a = set(audit_map)
    p = set(profile_map)
    r = set(readiness_map)
    if a != p or a != r:
        raise RolloutError(
            "repository sets must match across audit/profiles/readiness: "
            f"audit_only={sorted(a-p-r)}, profiles_only={sorted(p-a-r)}, readiness_only={sorted(r-a-p)}"
        )

    for repo in sorted(a):
        audit_sha = audit_map[repo].get("head_sha")
        profile_sha = profile_map[repo].get("source_sha")
        ready_sha = readiness_map[repo].get("source_sha")
        if not (isinstance(audit_sha, str) and isinstance(profile_sha, str) and isinstance(ready_sha, str)):
            raise RolloutError(f"{repo}: missing source SHA in one or more inputs")
        if profile_sha != audit_sha:
            raise RolloutError(f"{repo}: profile source_sha {profile_sha} != audit head_sha {audit_sha}")
        if ready_sha != audit_sha:
            raise RolloutError(f"{repo}: readiness source_sha {ready_sha} != audit head_sha {audit_sha}")
        native_target = profile_map[repo].get("native_target")
        if native_target not in {"3ds", "3ds-native"}:
            raise RolloutError(f"{repo}: native_target must be 3ds or 3ds-native")
        targets = profile_map[repo].get("targets")
        if not isinstance(targets, list) or "verify-3ds" not in targets:
            raise RolloutError(f"{repo}: verify-3ds target missing in profile")
    return audit_map, profile_map, readiness_map


def _select_current_version(readiness_row: dict[str, Any]) -> str:
    tags = readiness_row.get("tags")
    if not isinstance(tags, list):
        return "untagged"
    semvers: list[tuple[int, int, int, str]] = []
    for tag_obj in tags:
        if not isinstance(tag_obj, dict):
            continue
        tag = tag_obj.get("tag")
        if not isinstance(tag, str):
            continue
        m = SEMVER_RE.match(tag)
        if not m:
            continue
        semvers.append((int(m.group(1)), int(m.group(2)), int(m.group(3)), tag))
    if not semvers:
        return "untagged"
    semvers.sort()
    return semvers[-1][3]


def _release_channel(readiness_row: dict[str, Any]) -> str:
    stable_releases = readiness_row.get("stable_releases")
    if isinstance(stable_releases, list) and stable_releases:
        return "stable"
    return "wip"


def _default_reason(readiness_row: dict[str, Any]) -> str:
    blockers = readiness_row.get("blockers")
    if isinstance(blockers, list) and blockers:
        return str(blockers[0])
    return "Publishing blocked pending exact-source QA/provenance clearance"


def _json_compact(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def _load_template(name: str, templates_dir: Path) -> str:
    path = templates_dir / name
    if not path.is_file():
        raise RolloutError(f"missing template: {path}")
    return path.read_text(encoding="utf-8")


def _render_template(raw: str, values: dict[str, str]) -> str:
    out = raw
    for key, val in values.items():
        out = out.replace("{{" + key + "}}", val)
    return out


def _build_policy(repo: str, profile_row: dict[str, Any], readiness_row: dict[str, Any]) -> dict[str, Any]:
    reason = _default_reason(readiness_row).strip()
    if not reason:
        reason = "Publishing blocked pending exact-source QA/provenance clearance"
    return {
        "schema": 1,
        "repo": repo,
        "publish_enabled": False,
        "channel": _release_channel(readiness_row),
        "reason": reason,
        "native_target": profile_row["native_target"],
        "artifact_dir": "build/3ds",
        "cia_asset": f"{repo}.cia",
        "host_commands": [["make", "test"]],
        "native_commands": [["make", profile_row["native_target"]], ["make", "verify-3ds"]],
        "extra_engine_check": repo in EXTRA_ENGINE_REPOS,
    }


def _canonical_links(repo: str) -> dict[str, str]:
    return {
        "REPO_URL": f"https://github.com/lafiabrew/{repo}",
        "RELEASES_URL": f"https://github.com/lafiabrew/{repo}/releases",
        "HUB_URL": "https://github.com/lafiabrew/3ds_hub",
        "HUB_PAGES_URL": "https://lafiabrew.github.io/3ds_hub/",
    }


def _build_repo_payload(
    repo: str,
    audit_row: dict[str, Any],
    profile_row: dict[str, Any],
    readiness_row: dict[str, Any],
    kit_ref: str,
    templates_dir: Path,
) -> dict[str, Any]:
    current_version = _select_current_version(readiness_row)
    recommended_initial_version = readiness_row.get("recommended_initial_version") or "n/a"
    policy = _build_policy(repo, profile_row, readiness_row)

    blockers = readiness_row.get("blockers")
    blockers_list: list[str] = [str(x) for x in blockers] if isinstance(blockers, list) else []
    blockers_md = "\n".join(f"- {b}" for b in blockers_list) if blockers_list else "- None reported"

    links = _canonical_links(repo)
    values = {
        "REPO": repo,
        "KIT_SHA": kit_ref,
        "SOURCE_SHA": str(audit_row["head_sha"]),
        "CURRENT_VERSION": current_version,
        "RECOMMENDED_INITIAL_VERSION": str(recommended_initial_version),
        "CHANNEL": policy["channel"],
        "STATUS": str(readiness_row.get("eligibility", "unknown")),
        "PUBLISH_ENABLED": "false",
        "CI_CONFIGURED": str(readiness_row.get("ci_configured", False)).lower(),
        "CI_EXECUTED": str(readiness_row.get("ci_executed", False)).lower(),
        "REVIEWED": str(readiness_row.get("reviewed", False)).lower(),
        "PUBLISHED_EXISTING": str(readiness_row.get("published_existing", False)).lower(),
        "PHYSICAL_TEST": str(readiness_row.get("physically_tested", "not observed")),
        "BLOCKERS_MD": blockers_md,
        "NATIVE_TARGET": str(profile_row["native_target"]),
        "REPO_URL": links["REPO_URL"],
        "RELEASES_URL": links["RELEASES_URL"],
        "HUB_URL": links["HUB_URL"],
        "HUB_PAGES_URL": links["HUB_PAGES_URL"],
    }

    workflow_text = _render_template(_load_template("homebrew-release.yml.in", templates_dir), values)
    policy_values = dict(values)
    policy_values["REASON"] = json.dumps(policy["reason"])[1:-1]
    policy_values["EXTRA_ENGINE_CHECK"] = "true" if policy["extra_engine_check"] else "false"
    policy_text = _render_template(_load_template("homebrew-release.json", templates_dir), policy_values)
    try:
        parsed_policy = json.loads(policy_text)
    except json.JSONDecodeError as exc:
        raise RolloutError(f"policy template rendered invalid JSON for {repo}: {exc}") from exc
    policy_text = _json_compact(parsed_policy)
    releasing_text = _render_template(_load_template("RELEASING.md", templates_dir), values)

    files = {
        ".github/workflows/homebrew-release.yml": workflow_text,
        ".github/homebrew-release.json": policy_text,
        "docs/RELEASING.md": releasing_text,
    }
    file_meta = {
        path: {
            "path": path,
            "sha256": _sha256_bytes(content.encode("utf-8")),
            "bytes": len(content.encode("utf-8")),
        }
        for path, content in files.items()
    }

    return {
        "repo": repo,
        "source_sha": audit_row["head_sha"],
        "branch": audit_row.get("branch", "main"),
        "current_version": current_version,
        "recommended_initial_version": recommended_initial_version,
        "next_existing_version": readiness_row.get("next_existing_version"),
        "status": readiness_row.get("eligibility", "unknown"),
        "publish_enabled": False,
        "channel": policy["channel"],
        "reason": policy["reason"],
        "ci_configured": readiness_row.get("ci_configured", False),
        "ci_executed": readiness_row.get("ci_executed", False),
        "reviewed": readiness_row.get("reviewed", False),
        "published_existing": readiness_row.get("published_existing", False),
        "physically_tested": readiness_row.get("physically_tested", "not observed"),
        "blockers": blockers_list,
        "expected_commands": {
            "host_commands": policy["host_commands"],
            "native_commands": policy["native_commands"],
        },
        "rendered_files": file_meta,
        "rendered_contents": files,
    }


def _cmd_plan(args: argparse.Namespace) -> int:
    _require_kit_ref(args.kit_ref)
    audit = _read_json(Path(args.audit))
    profiles = _read_json(Path(args.profiles))
    readiness = _read_json(Path(args.readiness))
    audit_map, profile_map, readiness_map = _validate_inputs(audit, profiles, readiness)

    templates_dir = Path(args.templates_dir)
    repos = sorted(audit_map)
    plan_rows = [
        _build_repo_payload(
            repo,
            audit_map[repo],
            profile_map[repo],
            readiness_map[repo],
            args.kit_ref,
            templates_dir,
        )
        for repo in repos
    ]

    output = {
        "generated_utc": _utc_now(),
        "mode": "plan",
        "kit_ref": args.kit_ref,
        "input_files": {
            "audit": str(Path(args.audit)),
            "profiles": str(Path(args.profiles)),
            "readiness": str(Path(args.readiness)),
        },
        "repos": plan_rows,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_json_compact(output), encoding="utf-8")
    print(f"wrote plan for {len(plan_rows)} repos: {out_path}")
    return 0


def _git(repo_dir: Path, *argv: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["git", "-C", str(repo_dir), *argv]
    cp = subprocess.run(cmd, text=True, capture_output=True)
    if check and cp.returncode != 0:
        raise RolloutError(f"git failed ({' '.join(argv)}): {cp.stderr.strip()}")
    return cp


def _ensure_clean(repo_dir: Path) -> None:
    cp = _git(repo_dir, "status", "--porcelain", check=True)
    if cp.stdout.strip():
        raise RolloutError(f"{repo_dir.name}: repository is dirty; apply requires clean working tree")


def _existing_open_prs_count(path: Path | None) -> int:
    if path is None:
        return 0
    data = _read_json(path)
    if not isinstance(data, list):
        raise RolloutError("open PRs input must be a JSON list")
    return len(data)


def _write_if_safe(path: Path, content: str) -> tuple[str, str]:
    target_exists = path.exists()
    if target_exists:
        if path.is_symlink():
            raise RolloutError(f"refuse to overwrite symlink: {path}")
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            return "unchanged", _sha256_bytes(existing.encode("utf-8"))
        raise RolloutError(f"conflict: existing file differs: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return "created", _sha256_bytes(content.encode("utf-8"))


def _cmd_apply(args: argparse.Namespace) -> int:
    if args.max_open_prs > 5:
        raise RolloutError("max-open-prs cannot exceed 5")
    plan = _read_json(Path(args.plan))
    if plan.get("mode") != "plan":
        raise RolloutError("plan JSON has unexpected mode")
    kit_ref = plan.get("kit_ref")
    if kit_ref != args.kit_ref:
        raise RolloutError("--kit-ref mismatch with plan")
    _require_kit_ref(str(kit_ref))

    open_prs = _existing_open_prs_count(Path(args.open_prs_json) if args.open_prs_json else None)
    if open_prs > args.max_open_prs:
        raise RolloutError(f"open PR cap exceeded ({open_prs} > {args.max_open_prs})")

    repos = plan.get("repos")
    if not isinstance(repos, list):
        raise RolloutError("plan missing repos[]")

    expected_heads = _read_json(Path(args.expected_heads)) if args.expected_heads else {}
    if not isinstance(expected_heads, dict):
        raise RolloutError("--expected-heads must be JSON object {repo: sha}")

    root = Path(args.repos_root)
    receipts: list[dict[str, Any]] = []
    for row in repos:
        repo = row.get("repo")
        if not isinstance(repo, str):
            raise RolloutError("repo row missing repo")
        repo_dir = root / repo
        if not repo_dir.is_dir():
            raise RolloutError(f"missing repo dir: {repo_dir}")

        _ensure_clean(repo_dir)
        branch = _git(repo_dir, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if branch != args.expected_branch:
            raise RolloutError(f"{repo}: expected branch {args.expected_branch}, got {branch}")

        head_before = _git(repo_dir, "rev-parse", "HEAD").stdout.strip()
        expected = expected_heads.get(repo)
        if expected and head_before != expected:
            raise RolloutError(f"{repo}: HEAD changed before apply ({head_before} != expected {expected})")

        rendered = row.get("rendered_contents")
        if not isinstance(rendered, dict):
            raise RolloutError(f"{repo}: missing rendered_contents")

        file_changes: list[dict[str, Any]] = []
        for rel in OWNED_PATHS:
            content = rendered.get(rel)
            if not isinstance(content, str):
                raise RolloutError(f"{repo}: missing rendered content for {rel}")
            path = repo_dir / rel
            if args.dry_run:
                state = "would-create" if not path.exists() else "unchanged" if path.read_text(encoding="utf-8") == content else "conflict"
                if state == "conflict":
                    raise RolloutError(f"conflict: existing file differs: {path}")
                digest = _sha256_bytes(content.encode("utf-8"))
            else:
                state, digest = _write_if_safe(path, content)
            file_changes.append({"path": rel, "state": state, "sha256": digest})

        # reprobe HEAD immediately before any hypothetical remote write
        head_after = _git(repo_dir, "rev-parse", "HEAD").stdout.strip()
        if head_after != head_before:
            raise RolloutError(f"{repo}: HEAD changed during apply; aborting for race safety")

        receipts.append({"repo": repo, "head": head_before, "changes": file_changes, "dry_run": args.dry_run})

    output = {
        "generated_utc": _utc_now(),
        "mode": "apply",
        "dry_run": args.dry_run,
        "kit_ref": args.kit_ref,
        "repos_root": str(root),
        "expected_branch": args.expected_branch,
        "open_prs_seen": open_prs,
        "receipts": receipts,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(_json_compact(output), encoding="utf-8")
    print(f"wrote apply receipt for {len(receipts)} repos: {out_path}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Safe rollout planner for homebrew release policy/docs/workflow")
    sub = p.add_subparsers(dest="cmd", required=True)

    plan = sub.add_parser("plan", help="read-only planner")
    plan.add_argument("--audit", required=True, help="path to REPO_AUDIT.json")
    plan.add_argument("--profiles", required=True, help="path to BUILD_PROFILES.json")
    plan.add_argument("--readiness", required=True, help="path to RELEASE_READINESS.json")
    plan.add_argument("--kit-ref", required=True, help="immutable 40-char hub commit SHA")
    plan.add_argument("--output", required=True, help="output plan JSON path")
    plan.add_argument("--templates-dir", default="templates", help="template directory")
    plan.set_defaults(func=_cmd_plan)

    apply = sub.add_parser("apply", help="apply generated plan to local clones")
    apply.add_argument("--plan", required=True, help="plan JSON generated by plan command")
    apply.add_argument("--kit-ref", required=True, help="must match plan kit_ref")
    apply.add_argument("--repos-root", required=True, help="directory containing per-repo clones")
    apply.add_argument("--output", required=True, help="apply receipt path")
    apply.add_argument("--dry-run", action="store_true", help="validate only; do not write files")
    apply.add_argument("--expected-branch", default="main", help="expected checked-out branch")
    apply.add_argument("--expected-heads", help="JSON object mapping repo->expected head SHA")
    apply.add_argument("--open-prs-json", help="JSON list for current open rollout PRs")
    apply.add_argument("--max-open-prs", type=int, default=5, help="global rollout PR cap (<=5)")
    apply.set_defaults(func=_cmd_apply)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except RolloutError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
