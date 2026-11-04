#!/usr/bin/env python3
"""Dry-run-first enrollment of standalone Magento modules. Requires Python 3.9+, gh, git."""

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRANCH = "ci-templates/release-please-enrollment"
TITLE = "ci: configure release please"
MARKER = "Enrollment-Tool: studioraz/ci-templates"
SEMVER = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
FILES = {
    ".github/workflows/release-please.yml",
    ".github/workflows/pr-title.yml",
    "release-please-config.json",
    ".release-please-manifest.json",
    "composer.json",
    "README.md",
}


class Blocked(RuntimeError):
    pass


class Excluded(Blocked):
    pass


def run(*args, cwd=None):
    try:
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=True, check=False, timeout=180)
    except subprocess.TimeoutExpired as error:
        raise Blocked(f"{args[0]} {args[1]} timed out; no success assumed") from error
    if result.returncode:
        # Never print command output: authenticated transports can include credentials.
        status = re.search(r"\bHTTP (\d{3})\b", result.stderr)
        http = f", HTTP {status[1]}" if status else ""
        raise Blocked(f"{args[0]} {args[1]} failed (exit {result.returncode}{http}); "
                      "check authentication/access and retry")
    return result.stdout.strip()


def api(endpoint):
    try:
        return json.loads(run("gh", "api", endpoint))
    except Blocked as error:
        raise Blocked(f"GitHub API {endpoint}: {error}") from error


def pages(endpoint):
    try:
        return json.loads(run("gh", "api", "--paginate", "--slurp", endpoint))
    except Blocked as error:
        raise Blocked(f"GitHub API {endpoint}: {error}") from error


def version(value):
    match = SEMVER.fullmatch(value)
    if not match:
        raise Blocked(f"Not a stable SemVer: {value!r}")
    return tuple(map(int, match.groups()))


def read_json(path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def write_json(path, value):
    text = json.dumps(value, indent=2, ensure_ascii=True) + "\n"
    if not path.exists() or read_json(path) != value:
        path.write_text(text)


def check_paths(clone):
    for name in FILES | {".github", ".github/workflows"}:
        if (clone / name).is_symlink():
            raise Blocked(f"Symlink in enrollment path {name}; refusing external reads/writes")
    for path in (clone / ".github/workflows").glob("*"):
        if not path.is_file() or path.is_symlink():
            raise Blocked("Unsupported entry in .github/workflows")


def baseline(clone, releases, initial):
    tags = run("git", "tag", "--list", cwd=clone).splitlines()
    reachable = set(run("git", "tag", "--merged", "HEAD", cwd=clone).splitlines())
    stable = [tag for tag in tags if SEMVER.fullmatch(tag)]
    if any(tag not in reachable for tag in stable):
        raise Blocked("Stable tags exist outside the release branch; baseline needs manual review")
    for release in releases:
        if not release["draft"] and not release["prerelease"]:
            tag = release["tag_name"]
            if not SEMVER.fullmatch(tag) or tag not in reachable:
                raise Blocked(f"Published release {tag!r} cannot be verified against release-branch history")
    if stable:
        if initial:
            raise Blocked("--initial-version cannot override existing tagged releases")
        selected = max(stable, key=version)
        if any(re.match(r"^v?\d+\.\d+\.\d+-", tag) for tag in tags):
            raise Blocked("Prerelease tags require manual baseline review")
        return selected.lstrip("v"), f"highest stable reachable tag {selected}"
    if tags or releases:
        raise Blocked("Non-stable tag/release history requires manual baseline review")
    if not initial:
        raise Blocked("Untagged module: provide explicit --initial-version X.Y.Z intent")
    if version(initial) == (0, 0, 0):
        raise Blocked("Initial release must be greater than 0.0.0")
    return "0.0.0", f"untagged; one-time Release-As: {initial}"


def prepare(clone, branch, releases, initial):
    check_paths(clone)
    composer = read_json(clone / "composer.json", {})
    if composer.get("type") != "magento2-module":
        raise Excluded("Not a production magento2-module Composer package")
    if re.search(r"(?:template|example|sample|demo|test)(?:[-_]|$)", composer.get("name", "").split("/")[-1], re.I):
        raise Excluded("Template/example/test package excluded")
    selected, evidence = baseline(clone, releases, initial)
    config_path = clone / "release-please-config.json"
    config = read_json(config_path, {})
    if not isinstance(config, dict):
        raise Blocked("Config must be a JSON object")
    packages = config.get("packages", {".": {}})
    if not isinstance(packages, dict) or set(packages) != {"."} or not isinstance(packages["."], dict):
        raise Blocked("Only standalone root packages are supported")
    if any(key in obj for obj in (config, packages["."]) for key in ("release-as", "bootstrap-sha", "last-release-sha")):
        raise Blocked("Existing version/history overrides need manual review")
    base = read_json(ROOT / "actions/release-please-config/release-please-config.base.json")
    if any(key in packages["."] and packages["."][key] != value for key, value in base.items()):
        raise Blocked("Package overrides conflict with shared defaults")
    manifest_path = clone / ".release-please-manifest.json"
    manifest = read_json(manifest_path, {".": selected})
    if not isinstance(manifest, dict) or set(manifest) != {"."}:
        raise Blocked("Manifest must contain only the root package")
    if version(manifest["."]) < version(selected):
        raise Blocked("Existing manifest is behind verified release history; will not reset it")
    if initial and manifest["."] != "0.0.0":
        raise Blocked("Initial release intent conflicts with existing manifest")
    workflow_dir = clone / ".github/workflows"
    for path in sorted(workflow_dir.glob("*")):
        text = path.read_text()
        if path.name not in ("release-please.yml", "pr-title.yml") and re.search(
            r"release-please|release-calver|softprops/action-gh-release|ncipollo/release-action|gh release create|git (?:push.*--tags|tag)|semantic-release|release-drafter|action/create-release", text, re.I
        ):
            raise Blocked(f"Competing release publisher: {path.relative_to(clone)}")
    release = (ROOT / "callers/release-please.yml").read_text().split("  # Optional:")[0].rstrip() + "\n"
    release = release.replace("branches: [master]", "branches: [" + json.dumps(branch) + "]")
    pr_title = (ROOT / "scripts/release-please-pr-title.yml").read_text()
    for name, desired in (("release-please.yml", release), ("pr-title.yml", pr_title)):
        path = workflow_dir / name
        if path.exists() and path.read_text() != desired:
            raise Blocked(f"Existing {path.relative_to(clone)} differs; will not overwrite project workflow")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(desired)
    if "version" in composer:
        # Inspect tracked consumers before removing Composer's explicit root version.
        result = subprocess.run(
            ["git", "grep", "-n", "-I", "-i", "-E",
             r"getPrettyVersion|InstalledVersions::|getRootPackage|composer.{0,80}version|version.{0,80}composer",
             "--", "*.php", "*.phtml", "*.json", "*.xml", "*.yml", "*.yaml", "*.sh",
             "*.js", "*.ts", "*.toml", ":!composer.json", ":!composer.lock"],
            cwd=clone, text=True, capture_output=True, check=False, timeout=30,
        )
        if result.returncode not in (0, 1):
            raise Blocked("Composer version consumer scan failed")
        if result.stdout or (clone / "composer.lock").exists():
            paths = sorted({line.split(":", 1)[0] for line in result.stdout.splitlines()})
            raise Blocked("Explicit Composer version has potential consumers "
                          f"({', '.join(paths) or 'composer.lock'}); review migration manually")
        del composer["version"]
        path = clone / "composer.json"
        text = path.read_text()
        migrated, count = re.subn(
            r'^[ \t]*"version"[ \t]*:[ \t]*"(?:[^"\\]|\\.)*",[ \t]*\r?\n',
            "", text, flags=re.M,
        )
        if count != 1 or json.loads(migrated) != composer:
            raise Blocked("Composer version formatting needs manual removal; refusing unrelated JSON rewrites")
        path.write_text(migrated)
    write_json(config_path, {**config, **base, "packages": packages})
    write_json(manifest_path, manifest)
    readme = clone / "README.md"
    text = readme.read_text() if readme.exists() else ""
    section = (
        "## Releases\n\n"
        "Releases follow the [shared Release Please guide]"
        "(https://github.com/studioraz/ci-templates/blob/master/docs/release-please.md).\n"
        "Use Conventional Commit PR titles (`feat: add support`, `fix: correct behavior`).\n"
        "Squash merges use the PR title and body; single-commit PRs must have a matching commit title.\n\n"
        f"Pushes to `{branch}`, the Monday 06:00 UTC schedule and manual runs maintain the release PR "
        "and synchronize shared configuration.\n"
        "Merging a release PR creates a GitHub Release and an unprefixed SemVer tag, "
        "and updates the root `CHANGELOG.md`.\n"
        + (f"The manifest starts at `0.0.0`; preserve the onboarding PR's one-time "
           f"`Release-As: {initial}` footer in the squash commit. There is no permanent override.\n"
           if initial else f"Enrollment preserves existing release history (verified baseline `{selected}`).\n")
        + "\nThe optional `RELEASE_TOKEN` is forwarded to the shared workflow. Without it, "
        "`GITHUB_TOKEN` is used and bot-created PRs do not trigger PR-title CI. Supply a PAT or "
        "GitHub App token when those checks are required.\n"
    )
    if re.search(r"^## Releases\s*$", text, re.M):
        if section not in text:
            raise Blocked("Existing README Releases section differs; manual integration required")
    else:
        readme.write_text(text.rstrip() + "\n\n" + section)
    return manifest["."], evidence


def audit(repo, metadata):
    actions = api(f"repos/{repo}/actions/permissions")
    workflow = api(f"repos/{repo}/actions/permissions/workflow")
    rules = api(f"repos/{repo}/rulesets?includes_parents=true")
    branch = metadata["default_branch"]
    from urllib.parse import quote
    protection = api(f"repos/{repo}/branches/{quote(branch, safe='')}")
    legacy_protection = (
        api(f"repos/{repo}/branches/{quote(branch, safe='')}/protection")
        if protection["protected"] else None
    )
    # Legacy tag protections are retired by GitHub; active tag rules live in rulesets.
    rule_details = [api(f"repos/{repo}/rulesets/{rule['id']}?includes_parents=true") for rule in rules]
    blockers = []
    if not actions["enabled"] or actions.get("allowed_actions") != "all" or actions.get("sha_pinning_required"):
        blockers.append("Actions disabled/restricted or SHA pinning required; review reusable and nested action allowlists")
        if actions.get("allowed_actions") == "selected":
            actions["selected"] = api(f"repos/{repo}/actions/permissions/selected-actions")
    if workflow["default_workflow_permissions"] != "write" or not workflow["can_approve_pull_request_reviews"]:
        blockers.append("Actions write/create-PR permissions require approval")
    if (not metadata["allow_squash_merge"] or metadata["allow_merge_commit"] or metadata["allow_rebase_merge"]
            or metadata.get("squash_merge_commit_title") != "PR_TITLE"
            or metadata.get("squash_merge_commit_message") != "PR_BODY"):
        blockers.append("Approve squash-only + PR_TITLE/PR_BODY repository settings before merge")
    if protection["protected"] or rules:
        blockers.append("Protected branch/rulesets: review required checks, bypasses and tag creation before merge")
    return {"actions": actions, "workflow_permissions": workflow, "rulesets": rule_details,
            "branch_protected": protection["protected"], "branch_protection": legacy_protection,
            "merge_blockers": blockers,
            "token": "RELEASE_TOKEN effectiveness unknown (organization secret metadata not queried); "
                     "GITHUB_TOKEN fallback does not trigger bot PR CI. Do not require unavailable checks."}


def enroll(repo, args, user, report=None):
    report = report if report is not None else {"repo": repo}
    if not re.fullmatch(r"studioraz/magento2-[A-Za-z0-9_.-]+", repo):
        raise Blocked("Only explicit studioraz/magento2-* repositories are supported")
    metadata = api(f"repos/{repo}")
    if metadata["fork"] or metadata["archived"] or metadata["disabled"]:
        return {"repo": repo, "status": "excluded", "reason": "fork, archived or disabled"}
    if metadata.get("is_template") or re.search(
        r"(?:^|[-_])(?:template|example|sample|demo|test)(?:[-_]|$)", repo.split("/")[-1], re.I
    ):
        return {"repo": repo, "status": "excluded", "reason": "template/example/test repository"}
    branch = metadata["default_branch"]
    releases = [item for page in pages(f"repos/{repo}/releases?per_page=100") for item in page]
    report.update(branch=branch, prerequisites=audit(repo, metadata))
    with tempfile.TemporaryDirectory(prefix="release-please-enroll-") as temp:
        clone = Path(temp) / "repo"
        run("gh", "repo", "clone", repo, str(clone), "--", "--quiet", "--no-checkout")
        run("git", "checkout", "--quiet", branch, cwd=clone)
        check_paths(clone)
        base_sha = run("git", "rev-parse", "HEAD", cwd=clone)
        existing_callers = [
            path for path in (clone / ".github/workflows").glob("*")
            if "studioraz/ci-templates/.github/workflows/release-please.yml@"
            in path.read_text()
        ]
        if existing_callers:
            if args.initial_version:
                raise Blocked("Existing enrollment cannot be re-bootstrapped with --initial-version")
            config = read_json(clone / "release-please-config.json", {})
            manifest = read_json(clone / ".release-please-manifest.json", {})
            if not isinstance(config, dict) or "." not in config.get("packages", {}) or "." not in manifest:
                raise Blocked("Existing enrollment is incomplete; manual integration required")
            version(manifest["."])
            report.update(status="already-enrolled", baseline=manifest["."],
                          baseline_evidence="Existing enrollment manifest preserved, not re-inferred",
                          conformance="Existing shared caller left untouched; not a new conformance certification")
            return report
        report["baseline"], report["baseline_evidence"] = prepare(clone, branch, releases, args.initial_version)
        run("git", "add", "--", *sorted(FILES), cwd=clone)
        report["diff"] = run("git", "diff", "--cached", "--stat", cwd=clone)
        report["patch"] = run("git", "diff", "--cached", cwd=clone)
        tree = run("git", "write-tree", cwd=clone)
        if not report["diff"]:
            report["status"] = "already-enrolled"
            return report
        prs = api(f"repos/{repo}/pulls?state=open&head=studioraz:{BRANCH}&per_page=100")
        refs = api(f"repos/{repo}/git/matching-refs/heads/{BRANCH}")
        exact_refs = [ref for ref in refs if ref["ref"] == f"refs/heads/{BRANCH}"]
        existing = prs[0] if len(prs) == 1 else None
        if exact_refs:
            if not existing or existing["user"]["login"] != user or existing["base"]["ref"] != branch:
                raise Blocked("Enrollment branch is not owned by this operator's open PR")
            run("git", "fetch", "--quiet", "origin", BRANCH, cwd=clone)
            commits = run("git", "rev-list", f"{base_sha}..FETCH_HEAD", cwd=clone).splitlines()
            if (not commits or MARKER not in (existing.get("body") or "")
                    or existing["title"] != TITLE or not existing["draft"]):
                raise Blocked("Enrollment branch contains unrecognized commits")
            for commit in commits:
                message = run("git", "show", "-s", "--format=%B", commit, cwd=clone)
                author = run("git", "show", "-s", "--format=%ae", commit, cwd=clone)
                if MARKER not in message or author != user + "@users.noreply.github.com":
                    raise Blocked("Enrollment branch contains commits not authored by this tool/operator")
            # Only tool-owned enrollment paths may be replaced; never force push.
            paths = set(run("git", "diff", "--name-only", f"{base_sha}...FETCH_HEAD", cwd=clone).splitlines())
            if not paths <= FILES:
                raise Blocked("Enrollment branch contains changes outside tool ownership")
            if run("git", "rev-parse", "FETCH_HEAD^{tree}", cwd=clone) == tree:
                report.update(status="existing-pr", pr=existing["html_url"])
                return report
            if run("git", "merge-base", base_sha, "FETCH_HEAD", cwd=clone) != base_sha:
                raise Blocked("Base moved since enrollment; manual rebase required (no force push)")
        elif prs:
            raise Blocked("Open enrollment PR without expected branch")
        report["status"] = "dry-run"
        if not args.apply:
            return report
        body = (
            f"{MARKER}\n\nPreseeds shared release and strict PR-title callers, config and manifest.\n\n"
            f"Baseline: {report['baseline']} ({report['baseline_evidence']}). "
            "No releases are reset. No repository settings are changed.\n\n"
            + "\n".join(f"- {item}" for item in report["prerequisites"]["merge_blockers"])
            + "\n\n" + report["prerequisites"]["token"]
            + "\n\nReview the diff and prerequisites before marking ready. Live release proof remains pending merge."
            + (f"\n\nRelease-As: {args.initial_version}" if args.initial_version else "")
        )
        message = TITLE + "\n\n" + MARKER + (
            f"\n\nRelease-As: {args.initial_version}" if args.initial_version else ""
        ) + "\n\nCo-authored-by: Copilot App <223556219+Copilot@users.noreply.github.com>"
        # Refuse races with the base used to generate this exact change.
        live = api(f"repos/{repo}/git/ref/heads/{branch}")["object"]["sha"]
        if live != base_sha:
            raise Blocked("Base branch changed during enrollment; retry")
        run("git", "read-tree", "--reset", "-u", base_sha, cwd=clone)
        run("git", "checkout", "--quiet", "-b", BRANCH, "FETCH_HEAD" if exact_refs else base_sha, cwd=clone)
        run("git", "read-tree", "--reset", "-u", tree, cwd=clone)
        run("git", "-c", f"user.name={user}", "-c", "user.email=" + user + "@users.noreply.github.com",
            "commit", "--quiet", "-m", message, cwd=clone)
        run("git", "push", "--quiet", "origin", f"HEAD:refs/heads/{BRANCH}", cwd=clone)
        if existing:
            run("gh", "api", "--method", "PATCH", f"repos/{repo}/pulls/{existing['number']}",
                "-f", f"title={TITLE}", "-f", f"body={body}")
            url = existing["html_url"]
        else:
            url = run("gh", "pr", "create", "--repo", repo, "--base", branch, "--head", BRANCH,
                      "--title", TITLE, "--body", body, "--draft")
        report.update(status="draft-pr", pr=url)
    return report


def discover():
    cutoff = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=365)
    result, excluded = [], []
    for page in pages("orgs/studioraz/repos?type=all&per_page=100"):
        for repo in page:
            if not repo["name"].startswith("magento2-"):
                continue
            reason = None
            if repo["fork"] or repo["archived"] or repo["disabled"]:
                reason = "fork, archived or disabled"
            elif dt.datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00")) < cutoff:
                reason = "no push within 365 days"
            if reason:
                excluded.append({"repo": repo["full_name"], "status": "excluded", "reason": reason})
            else:
                result.append(repo["full_name"])
    return sorted(result), excluded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--repo", action="append", help="Repeat for an explicit bounded selection")
    group.add_argument("--discover", action="store_true", help="Discover active nonfork org modules")
    parser.add_argument("--apply", action="store_true", help="Push owned branch and open/update draft PRs")
    parser.add_argument("--initial-version", help="Explicit first-release intent; single untagged --repo only")
    parser.add_argument("--report", type=Path, required=True, help="Local JSON report, including patches; no secrets")
    args = parser.parse_args()
    if args.initial_version and (args.discover or len(args.repo) != 1):
        parser.error("--initial-version requires exactly one explicit --repo")
    reports = []
    failed = False
    args.report.write_text("[]\n")
    try:
        run("gh", "auth", "status")
        user = api("user")["login"]
        access = api("repos/studioraz/ci-templates/actions/permissions/access")
        if access["access_level"] not in ("organization", "enterprise"):
            raise Blocked("Private shared workflows are not accessible to organization consumers")
        base_path = "actions/release-please-config/release-please-config.base.json"
        shared_sha = api(f"repos/studioraz/ci-templates/contents/{base_path}?ref=master")["sha"]
        if run("git", "hash-object", str(ROOT / base_path)) != shared_sha:
            raise Blocked("Local shared defaults differ from published @master; update/review source before enrollment")
        repos, reports = discover() if args.discover else (sorted(set(args.repo)), [])
        for repo in repos:
            report = {"repo": repo}
            try:
                report = enroll(repo, args, user, report)
            except Excluded as error:
                report.update(status="excluded", reason=str(error))
            except (Blocked, ValueError, OSError, TypeError, KeyError, subprocess.TimeoutExpired) as error:
                failed = True
                report.update(status="blocked", reason=str(error))
            report.update(shared_base_sha=shared_sha, shared_workflow_access=access["access_level"])
            reports.append(report)
            args.report.write_text(json.dumps(reports, indent=2) + "\n")
            print(f"{repo}: {report['status']}" + (f" - {report['reason']}" if "reason" in report else ""), flush=True)
    except (Blocked, ValueError, OSError, TypeError, KeyError) as error:
        failed = True
        reports.append({"status": "blocked", "reason": str(error)})
        print(str(error), file=sys.stderr)
    args.report.write_text(json.dumps(reports, indent=2) + "\n")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
