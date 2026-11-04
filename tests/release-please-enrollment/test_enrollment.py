import importlib.util
import json
import subprocess
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "enrollment", Path(__file__).resolve().parents[2] / "scripts/enroll-release-please.py"
)
tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tool)


class EnrollmentTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.git("init", "-q")
        (self.repo / "composer.json").write_text(json.dumps({
            "name": "studioraz/module-fixture", "version": "0.9.0", "type": "magento2-module"
        }, indent=2) + "\n")
        (self.repo / "README.md").write_text("# Fixture\n")
        self.git("add", ".")
        self.git("-c", "user.name=fixture", "-c", "user.email=fixture@example.org",
                 "commit", "-qm", "initial")

    def git(self, *args):
        return tool.run("git", *args, cwd=self.repo)

    def tag(self, value):
        self.git("tag", value)

    def prepare(self, branch="main", initial=None, releases=None):
        return tool.prepare(self.repo, branch, releases or [], initial)

    def test_numeric_tag_not_composer_or_date(self):
        for tag in ("1.9.0", "v1.10.0", "1.2.0"):
            self.tag(tag)
        baseline, _ = self.prepare()
        self.assertEqual(baseline, "1.10.0")
        self.assertNotIn("version", json.loads((self.repo / "composer.json").read_text()))
        caller = (self.repo / ".github/workflows/release-please.yml").read_text()
        self.assertIn('branches: ["main"]', caller)
        self.assertIn('cron: "0 6 * * 1"', caller)
        self.assertIn("secrets.RELEASE_TOKEN", caller)
        title = (self.repo / ".github/workflows/pr-title.yml").read_text()
        for setting in ("validate-single-commit: true", "single-commit-matches-title: true",
                        "ignore-labels: ignore-semantic-pull-request", "comment: true"):
            self.assertIn(setting, title)
        self.assertNotIn("Release-As:", (self.repo / "README.md").read_text())

    def test_idempotent_and_preserves_owned_config_manifest(self):
        self.tag("1.2.3")
        (self.repo / "release-please-config.json").write_text(json.dumps({
            "plugins": ["foo"], "packages": {".": {"extra-files": ["Version.php"]}}
        }))
        (self.repo / ".release-please-manifest.json").write_text('{".": "1.3.0"}\n')
        self.prepare()
        before = {p: p.read_bytes() for p in self.repo.rglob("*") if p.is_file() and ".git" not in p.parts}
        self.prepare()
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        config = json.loads((self.repo / "release-please-config.json").read_text())
        self.assertEqual(config["plugins"], ["foo"])
        self.assertEqual(config["packages"]["."]["extra-files"], ["Version.php"])
        self.assertEqual(json.loads((self.repo / ".release-please-manifest.json").read_text()), {".": "1.3.0"})

    def test_untagged_requires_intent(self):
        with self.assertRaisesRegex(tool.Blocked, "explicit"):
            self.prepare()
        self.assertEqual(self.prepare(initial="1.0.0")[0], "0.0.0")
        self.assertIn("Release-As: 1.0.0", (self.repo / "README.md").read_text())

    def test_no_reset(self):
        self.tag("1.6.0")
        with self.assertRaisesRegex(tool.Blocked, "cannot override"):
            self.prepare(initial="1.0.0")
        (self.repo / ".release-please-manifest.json").write_text('{".":"1.0.0"}')
        with self.assertRaisesRegex(tool.Blocked, "behind"):
            self.prepare()

    def test_divergent_tag(self):
        self.git("checkout", "-qb", "other")
        self.git("-c", "user.name=f", "-c", "user.email=f@f", "commit", "-q",
                 "--allow-empty", "-m", "other")
        self.tag("9.0.0")
        self.git("checkout", "-q", "-")
        with self.assertRaisesRegex(tool.Blocked, "outside"):
            self.prepare()

    def test_unverified_release_and_prerelease(self):
        self.tag("1.0.0")
        with self.assertRaisesRegex(tool.Blocked, "cannot be verified"):
            self.prepare(releases=[{"draft": False, "prerelease": False, "tag_name": "2.0.0"}])
        self.tag("2.0.0-rc.1")
        with self.assertRaisesRegex(tool.Blocked, "Prerelease"):
            self.prepare()

    def test_existing_workflow_not_overwritten(self):
        self.tag("1.0.0")
        directory = self.repo / ".github/workflows"
        directory.mkdir(parents=True)
        path = directory / "release-please.yml"
        path.write_text("custom workflow\n")
        with self.assertRaisesRegex(tool.Blocked, "will not overwrite"):
            self.prepare()
        self.assertEqual(path.read_text(), "custom workflow\n")

    def test_existing_readme_and_competing_publisher(self):
        self.tag("1.0.0")
        (self.repo / "README.md").write_text("# Fixture\n\n## Releases\nCustom\n")
        with self.assertRaisesRegex(tool.Blocked, "manual integration"):
            self.prepare()
        directory = self.repo / ".github/workflows"
        (directory / "publish.yml").write_text("uses: softprops/action-gh-release@v2\n")
        with self.assertRaisesRegex(tool.Blocked, "Competing"):
            self.prepare()

    def test_composer_consumer_blocks_migration(self):
        self.tag("1.0.0")
        (self.repo / "version.php").write_text("<?php $package->getPrettyVersion();")
        self.git("add", "version.php")
        with self.assertRaisesRegex(tool.Blocked, "consumers"):
            self.prepare()

    def test_license_prose_is_not_version_consumer(self):
        self.tag("1.6.0")
        (self.repo / "LICENCE").write_text("Access the composer package and upgrade the version.")
        self.git("add", "LICENCE")
        self.assertEqual(self.prepare()[0], "1.6.0")

    def test_non_module(self):
        (self.repo / "composer.json").write_text('{"type":"project"}')
        with self.assertRaisesRegex(tool.Blocked, "production"):
            self.prepare()

    def test_symlink_refused(self):
        (self.repo / "README.md").unlink()
        (self.repo / "README.md").symlink_to(self.repo / "composer.json")
        with self.assertRaisesRegex(tool.Blocked, "Symlink"):
            self.prepare()

    def test_template_repository_excluded(self):
        with patch.object(tool, "api", return_value={"fork": False, "archived": False, "disabled": False}):
            report = tool.enroll("studioraz/magento2-module-template", types.SimpleNamespace(), "fixture")
        self.assertEqual(report["status"], "excluded")

    def test_auth_failure_explicit(self):
        with patch.object(subprocess, "run", return_value=subprocess.CompletedProcess(
                ["gh"], 1, "", "secret transport details")):
            with self.assertRaisesRegex(tool.Blocked, "authentication") as raised:
                tool.api("user")
            self.assertNotIn("secret", str(raised.exception))

    def test_discovery_exclusions_and_activity(self):
        def repo(name, **kwargs):
            return {"name": name, "full_name": "studioraz/" + name, "fork": False,
                    "archived": False, "disabled": False, "pushed_at": "2099-01-01T00:00:00Z", **kwargs}
        data = [repo("magento2-good"), repo("magento2-fork", fork=True),
                repo("magento2-old", pushed_at="2000-01-01T00:00:00Z"),
                repo("magento2-archived", archived=True), repo("magento2-disabled", disabled=True),
                repo("unrelated")]
        with patch.object(tool, "pages", return_value=[data]):
            selected, excluded = tool.discover()
        self.assertEqual(selected, ["studioraz/magento2-good"])
        self.assertEqual(len(excluded), 4)

    def integration(self, initial=None, private=True):
        """Real git clone/push; mock only GitHub transport and settings responses."""
        self.remote = self.repo / "remote.git"
        branch = self.git("branch", "--show-current")
        tool.run("git", "clone", "--quiet", "--bare", str(self.repo), str(self.remote))
        repo = "studioraz/magento2-fixture"
        self.prs = []
        metadata = {
            "fork": False, "archived": False, "disabled": False, "default_branch": branch,
            "private": private,
            "allow_squash_merge": True, "allow_merge_commit": True, "allow_rebase_merge": True,
            "squash_merge_commit_title": "COMMIT_OR_PR_TITLE",
            "squash_merge_commit_message": "COMMIT_MESSAGES",
        }
        original_run = tool.run

        def real_run(*args, cwd=None):
            if cwd == self.remote and args[0] == "git":
                args = ("git", "--git-dir=" + str(self.remote), *args[1:])
            return original_run(*args, cwd=cwd)

        self.api_calls = []

        def fake_api(endpoint):
            self.api_calls.append(endpoint)
            suffix = endpoint.removeprefix(f"repos/{repo}")
            if not suffix:
                return metadata
            if suffix == "/actions/permissions":
                return {"enabled": True, "allowed_actions": "all"}
            if suffix == "/actions/permissions/workflow":
                return {"default_workflow_permissions": "write", "can_approve_pull_request_reviews": True}
            if suffix == "/rulesets?includes_parents=true":
                return []
            if suffix.startswith("/branches/"):
                return {"protected": False}
            if suffix.startswith("/pulls?"):
                return self.prs
            if suffix.startswith("/git/matching-refs/"):
                refs = real_run("git", "for-each-ref", "--format=%(refname)",
                                f"refs/heads/{tool.BRANCH}", cwd=self.remote)
                return [{"ref": ref} for ref in refs.splitlines()]
            if suffix.startswith("/git/ref/heads/"):
                return {"object": {"sha": real_run("git", "rev-parse", branch, cwd=self.remote)}}
            raise AssertionError(endpoint)

        def fake_run(*args, cwd=None):
            if args[:3] == ("gh", "repo", "clone"):
                return real_run("git", "clone", "--quiet", "--no-checkout", str(self.remote), args[4])
            if args[:3] == ("gh", "pr", "create"):
                self.prs.append({
                    "user": {"login": "fixture"}, "base": {"ref": branch}, "draft": True,
                    "body": args[args.index("--body") + 1], "title": tool.TITLE,
                    "number": 1, "html_url": "https://github.com/" + repo + "/pull/1",
                })
                return self.prs[0]["html_url"]
            if args[:2] == ("gh", "api"):
                self.prs[0]["body"] = next(arg[5:] for arg in args if arg.startswith("body="))
                return "{}"
            return real_run(*args, cwd=cwd)

        for patcher in (patch.object(tool, "api", side_effect=fake_api),
                        patch.object(tool, "pages", return_value=[[]]),
                        patch.object(tool, "run", side_effect=fake_run)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.args = types.SimpleNamespace(initial_version=initial, apply=False)
        return repo

    def test_apply_dry_run_idempotency_and_owned_update(self):
        self.tag("1.2.3")
        repo = self.integration()
        dry = tool.enroll(repo, self.args, "fixture")
        self.assertEqual(dry["status"], "dry-run")
        self.assertFalse(self.prs)
        self.assertIn("Approve squash-only", dry["prerequisites"]["merge_blockers"][0])
        self.args.apply = True
        applied = tool.enroll(repo, self.args, "fixture")
        self.assertEqual(applied["status"], "draft-pr")
        self.assertEqual(tool.enroll(repo, self.args, "fixture")["status"], "existing-pr")
        self.assertEqual(len(self.prs), 1)
        # A new shared default is an owned fast-forward update, never a force push.
        original_read = tool.read_json

        def changed_base(path, default=None):
            value = original_read(path, default)
            if path.name == "release-please-config.base.json":
                value["draft"] = False
            return value

        with patch.object(tool, "read_json", side_effect=changed_base):
            self.assertEqual(tool.enroll(repo, self.args, "fixture")["status"], "draft-pr")
        self.assertEqual(len(self.prs), 1)
        count = tool.run("git", "rev-list", "--count", f"HEAD..{tool.BRANCH}", cwd=self.remote)
        self.assertEqual(count, "2")

    def test_initial_footer_in_actual_commit_and_pr(self):
        repo = self.integration(initial="1.0.0")
        self.args.apply = True
        tool.enroll(repo, self.args, "fixture")
        commit = tool.run("git", "show", "-s", "--format=%B", tool.BRANCH, cwd=self.remote)
        self.assertIn("Release-As: 1.0.0", commit)
        self.assertIn("Release-As: 1.0.0", self.prs[0]["body"])
        self.assertNotIn("release-as", tool.run(
            "git", "show", f"{tool.BRANCH}:release-please-config.json", cwd=self.remote))

    def test_existing_enrollment_is_not_rewritten(self):
        self.tag("1.2.3")
        self.prepare()
        self.git("add", ".")
        self.git("-c", "user.name=fixture", "-c", "user.email=fixture@example.org",
                 "commit", "-qm", "enrolled")
        repo = self.integration()
        self.assertEqual(tool.enroll(repo, self.args, "fixture")["status"], "already-enrolled")
        self.assertFalse(self.prs)

    def test_unowned_branch_blocks(self):
        self.tag("1.0.0")
        repo = self.integration()
        tool.run("git", "branch", tool.BRANCH, cwd=self.remote)
        self.args.apply = True
        with self.assertRaisesRegex(tool.Blocked, "not owned"):
            tool.enroll(repo, self.args, "fixture")
        self.assertFalse(self.prs)

    def test_foreign_commit_blocks(self):
        self.tag("1.0.0")
        repo = self.integration()
        self.args.apply = True
        tool.enroll(repo, self.args, "fixture")
        self.prs[0]["user"]["login"] = "someone-else"
        with self.assertRaisesRegex(tool.Blocked, "not owned"):
            tool.enroll(repo, self.args, "fixture")

    def test_foreign_commit_on_owned_pr_blocks(self):
        self.tag("1.0.0")
        repo = self.integration()
        self.args.apply = True
        tool.enroll(repo, self.args, "fixture")
        tree = tool.run("git", "rev-parse", tool.BRANCH + "^{tree}", cwd=self.remote)
        foreign = tool.run(
            "git", "-c", "user.name=other", "-c", "user.email=other@example.org",
            "commit-tree", tree, "-p", tool.BRANCH, "-m", "Unrelated work", cwd=self.remote,
        )
        tool.run("git", "update-ref", "refs/heads/" + tool.BRANCH, foreign, cwd=self.remote)
        with self.assertRaisesRegex(tool.Blocked, "not authored"):
            tool.enroll(repo, self.args, "fixture")

    def test_api_error_reports_endpoint_and_http_without_transport_details(self):
        failure = subprocess.CompletedProcess(["gh"], 1, "", "secret transport details (HTTP 403)")
        with patch.object(subprocess, "run", return_value=failure):
            with self.assertRaisesRegex(tool.Blocked, "repos/example/actions/permissions") as raised:
                tool.api("repos/example/actions/permissions")
        self.assertIn("HTTP 403", str(raised.exception))
        self.assertNotIn("secret", str(raised.exception))

    def test_public_caller_private_source_is_blocked_before_apply(self):
        self.tag("1.0.0")
        repo = self.integration(private=False)
        self.args.apply = True
        with self.assertRaisesRegex(tool.Blocked, "Public callers"):
            tool.enroll(repo, self.args, "fixture")
        self.assertFalse(self.prs)
        self.args.apply = False
        report = {}
        with self.assertRaisesRegex(tool.Blocked, "Public callers"):
            tool.enroll(repo, self.args, "fixture", report)
        self.assertIn("patch", report)
        self.assertFalse(report["prerequisites"]["workflow_access_compatible"])

    def test_public_caller_public_source_compatible(self):
        self.tag("1.0.0")
        repo = self.integration(private=False)
        self.args.shared_private = False
        self.assertEqual(tool.enroll(repo, self.args, "fixture")["status"], "dry-run")

    def test_forks_excluded_even_explicit(self):
        with patch.object(tool, "api", return_value={"fork": True}):
            report = tool.enroll("studioraz/magento2-fork", types.SimpleNamespace(), "fixture")
        self.assertEqual(report["status"], "excluded")


if __name__ == "__main__":
    unittest.main()
