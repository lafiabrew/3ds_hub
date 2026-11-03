#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import stat
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

SEMVER_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
OWNED_PATHS = (
    ".github/workflows/homebrew-release.yml",
    ".github/homebrew-release.json",
    "docs/RELEASING.md",
)
# Current PUBLIC source contract, superseding stale private-engine candidates.
EXTRA_ENGINE_REPOS = {"3ds_foldquest"}
EXTRA_ENGINE_COMMAND = ["python3", "-m", "unittest", "discover", "-s", "tests", "-p", "test_contract.py", "-v"]


class RolloutError(RuntimeError):
    pass


def _read_json(path: Path) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique,
                          parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))
    except Exception as exc:  # pragma: no cover - exact message propagated
        raise RolloutError(f"failed to read JSON {path}: {exc}") from exc


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _require_kit_ref(kit_ref: str) -> None:
    if not isinstance(kit_ref, str) or not SHA40_RE.fullmatch(kit_ref):
        raise RolloutError("--kit-ref must be a full 40-char lowercase hex commit SHA")


REPO_RE = re.compile(r"^3ds_[a-z0-9][a-z0-9_]*$")
BRANCH = "rollout/homebrew-release"
TEMPLATES = Path(__file__).resolve().parents[1] / "templates"


def _repo_name(repo: Any) -> str:
    if not isinstance(repo, str) or not REPO_RE.fullmatch(repo) or repo == "3ds_hub":
        raise RolloutError("invalid or excluded public repository name")
    return repo


def _row_map(rows: list[dict[str, Any]], key: str = "repo") -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RolloutError("repository row must be an object")
        repo = _repo_name(row.get(key))
        if row.get("archived", False) is not False or row.get("private", False) is not False:
            raise RolloutError(f"{repo}: archived/private repository excluded")
        if row.get("full_name", f"lafiabrew/{repo}") != f"lafiabrew/{repo}":
            raise RolloutError(f"{repo}: foreign repository excluded")
        if repo in out:
            raise RolloutError(f"duplicate {key}: {repo}")
        out[repo] = row
    return out


def _validate_inputs(
    audit: dict[str, Any],
    profiles: dict[str, Any],
    readiness: dict[str, Any],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    if not all(isinstance(obj, dict) for obj in (audit, profiles, readiness)):
        raise RolloutError("audit/profiles/readiness must be objects")
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
    if not a:
        raise RolloutError("empty repository inputs are not admissible")
    if a != p or a != r:
        raise RolloutError(
            "repository sets must match across audit/profiles/readiness: "
            f"audit_only={sorted(a-p-r)}, profiles_only={sorted(p-a-r)}, readiness_only={sorted(r-a-p)}"
        )

    for repo in sorted(a):
        audit_sha = audit_map[repo].get("head_sha")
        profile_sha = profile_map[repo].get("source_sha")
        ready_sha = readiness_map[repo].get("source_sha")
        if not all(isinstance(s, str) and SHA40_RE.fullmatch(s) for s in (audit_sha, profile_sha, ready_sha)):
            raise RolloutError(f"{repo}: source SHA must be full lowercase hex")
        if audit_map[repo].get("branch") != "main":
            raise RolloutError(f"{repo}: audited default branch must be main")
        if profile_sha != audit_sha:
            raise RolloutError(f"{repo}: profile source_sha {profile_sha} != audit head_sha {audit_sha}")
        if ready_sha != audit_sha:
            raise RolloutError(f"{repo}: readiness source_sha {ready_sha} != audit head_sha {audit_sha}")
        ready = readiness_map[repo]
        for field in ("ci_configured", "ci_executed", "reviewed", "published_existing", "publish_enabled"):
            if field in ready and type(ready[field]) is not bool:
                raise RolloutError(f"{repo}: {field} must be a JSON boolean")
        if ready.get("publish_enabled", False):
            raise RolloutError(f"{repo}: initial rollout cannot enable publishing")
        native_target = profile_map[repo].get("native_target")
        if native_target not in {"3ds", "3ds-native"}:
            raise RolloutError(f"{repo}: native_target must be 3ds or 3ds-native")
        targets = profile_map[repo].get("targets")
        if not isinstance(targets, list) or "verify-3ds" not in targets:
            raise RolloutError(f"{repo}: verify-3ds target missing in profile")
        if native_target not in targets or "test" not in targets:
            raise RolloutError(f"{repo}: actual native/test target missing in profile")
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
        m = SEMVER_RE.fullmatch(tag)
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
        reason = str(blockers[0])
        if re.search(r"/(?:home|tmp|Users)/|gh[pousr]_|github_pat_|raw.session", reason, re.I):
            return "Private evidence omitted; exact-source approval remains blocked"
        return reason
    return "Publishing blocked pending exact-source QA/provenance clearance"


def _json_compact(obj: Any) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def _load_template(name: str, templates_dir: Path) -> str:
    path = templates_dir / name
    if not path.is_file():
        raise RolloutError(f"missing template: {path}")
    return path.read_text(encoding="utf-8")


def _render_template(raw: str, values: dict[str, str]) -> str:
    # Single pass: untrusted metadata cannot expand a second template token.
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: values.get(m[1], m[0]), raw)


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
    recommended_initial_version = "v0.1.0" if current_version == "untagged" else "n/a (derive next version from actual tags and reviewed changes)"
    policy = _build_policy(repo, profile_row, readiness_row)

    blockers = readiness_row.get("blockers")
    blockers_list: list[str] = [str(x) for x in blockers] if isinstance(blockers, list) else []
    def safe_md(value: Any) -> str:
        text = html.escape(str(value), quote=True)
        text = ''.join(c if c >= ' ' else ' ' for c in text)
        for char in ('`', '[', ']', '*', '_', '{', '}', '\\'):
            text = text.replace(char, f"&#{ord(char)};")
        # Never propagate private paths or raw session/credential-shaped metadata.
        if re.search(r"/(?:home|tmp|Users)/|gh[pousr]_|github_pat_|raw.session", text, re.I):
            return "Private evidence omitted; consult coordinator readiness ledger"
        return text
    blockers_md = "\n".join(f"- {safe_md(b)}" for b in blockers_list) if blockers_list else "- Exact-source QA/provenance approval not supplied"

    links = _canonical_links(repo)
    values = {
        "REPO": repo,
        "KIT_SHA": kit_ref,
        "SOURCE_SHA": str(audit_row["head_sha"]),
        "CURRENT_VERSION": current_version,
        "RECOMMENDED_INITIAL_VERSION": str(recommended_initial_version),
        "CHANNEL": policy["channel"],
        "STATUS": safe_md(readiness_row.get("eligibility", "unknown")),
        "PUBLISH_ENABLED": "false",
        "CI_CONFIGURED": str(readiness_row.get("ci_configured", False)).lower(),
        "CI_EXECUTED": str(readiness_row.get("ci_executed", False)).lower(),
        "REVIEWED": str(readiness_row.get("reviewed", False)).lower(),
        "PUBLISHED_EXISTING": str(readiness_row.get("published_existing", False)).lower(),
        "PHYSICAL_TEST": safe_md(readiness_row.get("physically_tested", "not observed")),
        "BLOCKERS_MD": blockers_md,
        "NATIVE_TARGET": str(profile_row["native_target"]),
        "EXTRA_ENGINE_BUILD_LINE": "python3 -m unittest discover -s tests -p test_contract.py -v &&\n" if policy["extra_engine_check"] else "",
        "EXTRA_ENGINE_NOTE": "The shared kit additionally requires regular nonempty tests/test_contract.py, collects at least one test, and rejects failures or skips; bare unittest discovery exit 0 with zero tests is not acceptance." if policy["extra_engine_check"] else "No separate Python contract suite is claimed for this public source; make test remains required.",
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
    if json.dumps(parsed_policy, sort_keys=True) != json.dumps(policy, sort_keys=True) or parsed_policy.get("publish_enabled") is not False:
        raise RolloutError("rendered policy differs from strict disabled schema")
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
            "extra_engine_command": EXTRA_ENGINE_COMMAND if policy["extra_engine_check"] else None,
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

    templates_dir = Path(args.templates_dir).resolve()
    if templates_dir != TEMPLATES:
        raise RolloutError("only installed trusted templates are supported")
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
        "schema": 1,
        "inputs": {"audit": audit, "profiles": profiles, "readiness": readiness},
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
        raise RolloutError(f"Git read-only probe failed: {argv[0]}")
    return cp


def _ensure_clean(repo_dir: Path) -> None:
    cp = _git(repo_dir, "status", "--porcelain", check=True)
    if cp.stdout.strip():
        raise RolloutError(f"{repo_dir.name}: repository is dirty; apply requires clean working tree")


def _gh(endpoint: str, *, paginated: bool = False) -> Any:
    argv = ["gh", "api"]
    if paginated:
        argv += ["--paginate", "--slurp"]
    argv.append(endpoint)
    cp = subprocess.run(argv, text=True, capture_output=True, timeout=60)
    if cp.returncode:
        # Do not echo transport output, which may contain secrets.
        raise RolloutError("GitHub read-only probe failed")
    try:
        result = json.loads(cp.stdout)
        if paginated:
            if not isinstance(result, list) or not all(isinstance(p, list) for p in result):
                raise ValueError()
            result = [row for page in result for row in page]
        return result
    except (ValueError, TypeError) as exc:
        raise RolloutError("invalid GitHub probe response") from exc


def _public_identity(repo: str) -> None:
    data = _gh(f"repos/lafiabrew/{repo}")
    if not isinstance(data, dict) or any((
        data.get("full_name") != f"lafiabrew/{repo}",
        data.get("private") is not False, data.get("archived") is not False,
        data.get("default_branch") != "main",
    )):
        raise RolloutError(f"{repo}: public identity/default main admission failed")


def _kit_preflight(kit_ref: str) -> None:
    _public_identity("3ds_hub")
    comparison = _gh(f"repos/lafiabrew/3ds_hub/compare/{kit_ref}...main")
    if not isinstance(comparison, dict) or not all(isinstance(comparison.get(key), dict) and comparison[key].get("sha") == kit_ref for key in ("base_commit", "merge_base_commit")) or comparison.get("status") not in {"ahead", "identical"}:
        raise RolloutError("kit pin is not reachable on actual public hub main")
    workflow = _gh(f"repos/lafiabrew/3ds_hub/contents/.github/workflows/homebrew-release.yml?ref={kit_ref}")
    if not isinstance(workflow, dict) or workflow.get("type") != "file" or workflow.get("path") != ".github/workflows/homebrew-release.yml" or type(workflow.get("size")) is not int or workflow["size"] <= 0:
        raise RolloutError("kit pin has no regular reusable workflow")


def _existing_open_prs_count(required: set[str]) -> int:
    # Enumerate actual organization repositories and every page of open pulls.
    # Canonical rollout namespace is reserved to the coordinator; no label required.
    repos = _gh("orgs/lafiabrew/repos?type=public&per_page=100", paginated=True)
    count = 0
    observed: set[str] = set()
    for repo in repos:
        if not isinstance(repo, dict) or not isinstance(repo.get("name"), str):
            raise RolloutError("malformed organization repository evidence")
        name = repo["name"]
        if not REPO_RE.fullmatch(name) or name == "3ds_hub":
            continue
        if name in observed:
            raise RolloutError("duplicate organization repository evidence")
        observed.add(name)
        # Include archived/private entries if returned: their open rollout PRs still count.
        pulls = _gh(f"repos/lafiabrew/{name}/pulls?state=open&per_page=100", paginated=True)
        for pull in pulls:
            if not isinstance(pull, dict) or not isinstance(pull.get("head"), dict) or not isinstance(pull["head"].get("ref"), str):
                raise RolloutError("malformed current open PR evidence")
            if pull["head"]["ref"].startswith(BRANCH):
                count += 1
    if not required <= observed:
        raise RolloutError("current organization probe omitted selected repositories")
    return count


def _safe_path(path: Path, *, directory: bool = False) -> None:
    # lstat every existing component, including dangling links; resolve() alone
    # would silently follow them. This also protects repos-root ancestors.
    parts = list(reversed(path.absolute().parents)) + [path.absolute()]
    for part in parts:
        try:
            mode = part.lstat().st_mode
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(mode):
            raise RolloutError("symlink path/ancestor refused")
        if part != path.absolute() or directory:
            if not stat.S_ISDIR(mode):
                raise RolloutError("path ancestor is not a directory")
        elif not stat.S_ISREG(mode):
            raise RolloutError("output must be a regular file")


def _validated_plan(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    plan = _read_json(Path(args.plan))
    if not isinstance(plan, dict) or set(plan) != {"schema", "inputs", "generated_utc", "mode", "kit_ref", "input_files", "repos"}:
        raise RolloutError("strict plan schema mismatch")
    if type(plan["schema"]) is not int or plan["schema"] != 1 or plan["mode"] != "plan":
        raise RolloutError("strict plan mode/schema mismatch")
    _require_kit_ref(args.kit_ref)
    if plan["kit_ref"] != args.kit_ref:
        raise RolloutError("--kit-ref mismatch with plan")
    if not isinstance(plan["generated_utc"], str) or not isinstance(plan["input_files"], dict) or set(plan["input_files"]) != {"audit", "profiles", "readiness"} or not all(isinstance(v, str) for v in plan["input_files"].values()):
        raise RolloutError("strict plan metadata schema mismatch")
    inputs = plan["inputs"]
    if not isinstance(inputs, dict) or set(inputs) != {"audit", "profiles", "readiness"}:
        raise RolloutError("plan inputs schema mismatch")
    a, p, r = _validate_inputs(inputs["audit"], inputs["profiles"], inputs["readiness"])
    expected = [_build_repo_payload(repo, a[repo], p[repo], r[repo], args.kit_ref, TEMPLATES) for repo in sorted(a)]
    # Independently regenerate content, hashes, sizes, policy and caller pin from
    # admitted inputs and this installed tool's templates, never trust plan text.
    if _json_compact(plan["repos"]) != _json_compact(expected):
        raise RolloutError("plan content/hash/policy/caller pin differs from independent rendering")
    selected = args.repo or list(a)
    if not selected or len(selected) != len(set(selected)) or not set(selected) <= set(a):
        raise RolloutError("unknown or duplicate selected repository")
    return plan, [row for row in expected if row["repo"] in selected]


def _repo_preflight(root: Path, row: dict[str, Any], *, prepared: bool = False) -> Path:
    repo = _repo_name(row["repo"])
    path = root / repo
    _safe_path(path, directory=True)
    if not path.is_dir() or _git(path, "rev-parse", "--show-toplevel").stdout.strip() != str(path):
        raise RolloutError(f"{repo}: not an exact Git root")
    # No linked worktrees/shared gitdir: require a standalone isolated clone.
    _safe_path(path / ".git", directory=True)
    origins = _git(path, "remote", "get-url", "--all", "origin").stdout.splitlines()
    if origins not in ([f"https://github.com/lafiabrew/{repo}.git"], [f"git@github.com:lafiabrew/{repo}.git"]):
        raise RolloutError(f"{repo}: origin is not the exact expected public repository")
    push_origins = _git(path, "remote", "get-url", "--push", "--all", "origin").stdout.splitlines()
    if push_origins != origins:
        raise RolloutError(f"{repo}: alternate push origin refused")
    _public_identity(repo)
    branch = _git(path, "symbolic-ref", "--short", "HEAD").stdout.strip()
    if branch != (BRANCH if prepared else "main"):
        raise RolloutError(f"{repo}: unexpected checked-out branch")
    head = _git(path, "rev-parse", "HEAD").stdout.strip()
    # Path safety precedes cleanliness so symlink ancestors, including dangling
    # ones recorded as untracked files, are explicitly rejected even on dry-run.
    _files_preflight(path, row, prepared=prepared)
    if prepared:
        _ensure_clean(path)
        if _git(path, "rev-parse", "HEAD^").stdout.strip() != row["source_sha"]:
            raise RolloutError(f"{repo}: prepared commit parent is not approved source")
        changed = _git(path, "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").stdout.splitlines()
        if set(changed) != set(OWNED_PATHS):
            raise RolloutError(f"{repo}: prepared commit must change exactly the three owned paths")
    elif head != row["source_sha"]:
        raise RolloutError(f"{repo}: HEAD changed from plan source pin")
    else:
        # Allow only already-identical, UNTRACKED generated outputs for retry.
        # Staged/unstaged tracked changes are always dirty; index is never changed.
        if _git(path, "diff", "--name-only").stdout or _git(path, "diff", "--cached", "--name-only").stdout:
            raise RolloutError(f"{repo}: dirty tracked/index files")
        untracked = _git(path, "ls-files", "--others", "--exclude-standard", "-z").stdout.split('\0')
        if any(f and f not in OWNED_PATHS for f in untracked):
            raise RolloutError(f"{repo}: dirty untracked files")
    # Actual remote freshness, not origin/main cache or local HEAD.
    remote = _git(path, "ls-remote", "--symref", "origin", "HEAD", "refs/heads/main").stdout.splitlines()
    if "ref: refs/heads/main\tHEAD" not in remote or f"{row['source_sha']}\trefs/heads/main" not in remote:
        raise RolloutError(f"{repo}: actual remote main changed or is not default")
    if _git(path, "rev-parse", "HEAD").stdout.strip() != head or _git(path, "symbolic-ref", "--short", "HEAD").stdout.strip() != branch:
        raise RolloutError(f"{repo}: HEAD changed during remote probe")
    if _git(path, "diff", "--name-only").stdout or _git(path, "diff", "--cached", "--name-only").stdout:
        raise RolloutError(f"{repo}: dirty files appeared during remote probe")
    unexpected = [f for f in _git(path, "ls-files", "--others", "--exclude-standard", "-z").stdout.split('\0') if f and (prepared or f not in OWNED_PATHS)]
    if unexpected:
        raise RolloutError(f"{repo}: dirty untracked files appeared during remote probe")
    return path


def _files_preflight(path: Path, row: dict[str, Any], *, prepared: bool = False) -> list[dict[str, Any]]:
    changes = []
    for rel in OWNED_PATHS:
        target = path / rel
        _safe_path(target)
        content = row["rendered_contents"][rel].encode("utf-8")
        if target.exists() and target.read_bytes() != content:
            raise RolloutError(f"{row['repo']}: conflict: existing file differs: {rel}")
        if prepared and not target.exists():
            raise RolloutError("prepared output missing")
        changes.append({"path": rel, "state": "unchanged" if target.exists() else "would-create", "sha256": _sha256_bytes(content)})
    return changes


def _create_exclusive(target: Path, data: bytes) -> None:
    # Walk with directory descriptors so a late ancestor symlink cannot redirect
    # an output outside its clone. No rollback/delete on I/O failure is attempted.
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for component in target.absolute().parts[1:-1]:
            try:
                os.mkdir(component, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        file_fd = os.open(target.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=fd)
        with os.fdopen(file_fd, 'wb') as stream:
            stream.write(data)
    finally:
        os.close(fd)


def _cmd_apply(args: argparse.Namespace) -> int:
    if not 1 <= args.max_open_prs <= 5:
        raise RolloutError("max-open-prs must be between 1 and 5")
    plan, rows = _validated_plan(args)
    if args.expected_branch != "main":
        raise RolloutError("only actual default main is admitted")
    heads = _read_json(Path(args.expected_heads)) if args.expected_heads else {}
    if not isinstance(heads, dict) or any(k not in {r['repo'] for r in rows} or v != next(r['source_sha'] for r in rows if r['repo'] == k) for k, v in heads.items()):
        raise RolloutError("HEAD changed: --expected-heads cannot override plan source pins")
    root = Path(args.repos_root).absolute()
    _safe_path(root, directory=True)
    output = Path(args.output).absolute()
    _safe_path(output)
    if output == root or root in output.parents:
        raise RolloutError("receipt must be outside repos-root")
    prepared = args.cmd == "verify-publish"
    receipts = []
    # Two complete global preflights. ALL selected repositories, paths, content,
    # actual remote heads and cap checked before the FIRST output write.
    for boundary in range(2):
        _kit_preflight(plan['kit_ref'])
        open_prs = _existing_open_prs_count({row['repo'] for row in rows})
        if open_prs + len(rows) > args.max_open_prs:
            raise RolloutError(f"open PR cap including pending batch exceeded ({open_prs}+{len(rows)} > {args.max_open_prs})")
        receipts = []
        for row in rows:
            path = _repo_preflight(root, row, prepared=prepared)
            changes = _files_preflight(path, row, prepared=prepared)
            receipts.append({"repo": row["repo"], "head": row["source_sha"], "changes": changes})
    if not args.dry_run and not prepared:
        for row in rows:
            for rel, content in row["rendered_contents"].items():
                target = root / row["repo"] / rel
                _safe_path(target)
                if target.exists():
                    if target.read_bytes() != content.encode("utf-8"):
                        raise RolloutError("late output conflict; preserve partial preparation and inspect")
                else:
                    _create_exclusive(target, content.encode("utf-8"))
    receipt = {"schema": 1, "generated_utc": _utc_now(), "mode": "publish-boundary-check" if prepared else "local-prepare",
               "dry_run": args.dry_run, "kit_ref": plan["kit_ref"], "open_prs_seen": open_prs,
               "pending_batch": len(rows), "receipts": receipts, "remote_writes": False}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_json_compact(receipt), encoding="utf-8")
    print(f"{'verified publish boundary' if prepared else 'local-only preparation'}: {len(rows)} repos; no push/PR performed")
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
    plan.add_argument("--templates-dir", default=str(TEMPLATES), help="installed trusted template directory only")
    plan.set_defaults(func=_cmd_plan)

    apply = sub.add_parser("apply", help="apply generated plan to local clones")
    apply.add_argument("--plan", required=True, help="plan JSON generated by plan command")
    apply.add_argument("--kit-ref", required=True, help="must match plan kit_ref")
    apply.add_argument("--repos-root", required=True, help="directory containing per-repo clones")
    apply.add_argument("--output", required=True, help="apply receipt path")
    apply.add_argument("--dry-run", action="store_true", help="validate only; do not write files")
    apply.add_argument("--expected-branch", default="main", help="expected checked-out branch")
    apply.add_argument("--expected-heads", help="JSON object mapping repo->expected head SHA")
    apply.add_argument("--repo", action="append", help="select repository (repeatable); cap includes entire pending batch")
    apply.add_argument("--max-open-prs", type=int, default=5, help="global rollout PR cap (<=5)")
    apply.set_defaults(func=_cmd_apply)

    verify = sub.add_parser("verify-publish", help="read-only check of prepared one-commit rollout branch before coordinator push/PR")
    for flag in ("plan", "kit-ref", "repos-root", "output"):
        verify.add_argument("--" + flag, required=True)
    verify.add_argument("--repo", action="append", required=True)
    verify.add_argument("--max-open-prs", type=int, default=5)
    verify.set_defaults(func=_cmd_apply, dry_run=True, expected_branch="main", expected_heads=None)
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (RolloutError, OSError, ValueError, TypeError, KeyError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
