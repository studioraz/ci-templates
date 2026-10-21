#!/usr/bin/env bash
#
# Scenario tests for actions/calver-release/calver-release.sh.
#
# Builds a throwaway repo with a bare "origin" and a stubbed `gh` that records
# its calls, then walks through the release lifecycle. Needs bash 4+, GNU
# coreutils/sed, git and jq (ubuntu-latest has them all).
#
# Usage: tests/calver-release/run.sh

set -euo pipefail

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/actions/calver-release/calver-release.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

export TZ=Asia/Jerusalem
export GITHUB_REPOSITORY=acme/shop
export GITHUB_SERVER_URL=https://github.com
export JIRA_BASE_URL=https://acme.atlassian.net
export GH_LOG="$WORK/gh.log"
export GIT_AUTHOR_NAME=test GIT_AUTHOR_EMAIL=test@example.com
export GIT_COMMITTER_NAME=test GIT_COMMITTER_EMAIL=test@example.com
unset GITHUB_OUTPUT

TODAY="$(date +%Y.%m.%d)"
YESTERDAY="$(date -d yesterday +%Y.%m.%d)"
FAILED=0

# --- gh stub -----------------------------------------------------------------
mkdir -p "$WORK/bin"
cat > "$WORK/bin/gh" <<'EOF'
#!/usr/bin/env bash
echo "gh $*" >> "$GH_LOG"
case "$1 $2" in
    "pr list")
        if [[ "$*" == *merged* ]]; then echo "${FAKE_MERGED:-}"; else echo "${FAKE_OPEN_PR:-}"; fi ;;
    "pr create") echo "https://github.com/acme/shop/pull/99" ;;
esac
exit 0
EOF
chmod +x "$WORK/bin/gh"
export PATH="$WORK/bin:$PATH"

# --- helpers -----------------------------------------------------------------
pass() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; FAILED=$((FAILED + 1)); }

expect_contains() { # haystack needle description
    if grep -qF -- "$2" <<< "$1"; then pass "$3"; else fail "$3 (missing: $2)"; fi
}
expect_not_contains() {
    if grep -qF -- "$2" <<< "$1"; then fail "$3 (unexpected: $2)"; else pass "$3"; fi
}

run_release() { # runs the script, prints its stdout+stderr
    : > "$GH_LOG"
    bash "$SCRIPT" 2>&1
}

dry_run() { DRY_RUN=1 bash "$SCRIPT" 2>&1; }

lock_versions() { # sets package versions in composer.lock: name=version ...
    local filter="." kv
    for kv in "$@"; do
        filter+=" | (.packages[] | select(.name == \"${kv%%=*}\") | .version) = \"${kv#*=}\""
    done
    jq --indent 4 "$filter" composer.lock > composer.lock.tmp && mv composer.lock.tmp composer.lock
}

# --- fixture -----------------------------------------------------------------
git init -q --bare "$WORK/origin.git"
git init -q -b main "$WORK/repo"
cd "$WORK/repo"
git remote add origin "$WORK/origin.git"
cat > composer.lock <<'EOF'
{
    "content-hash": "0",
    "packages": [
        {"name": "monolog/monolog", "version": "3.5.0"},
        {"name": "psr/log", "version": "2.0.0"}
    ],
    "packages-dev": [
        {"name": "phpunit/phpunit", "version": "10.5.0"}
    ]
}
EOF
printf '# Changelog\n' > CHANGELOG.md
echo 0.0.0.0 > VERSION
git add -A && git commit -qm "chore: initial commit"
git push -q origin main

echo "1. Only hidden commit types"
out="$(dry_run)"
expect_contains "$out" "No releasable changes" "no release PR without releasable commits"

echo "2. First release"
git commit -q --allow-empty -m "feat(checkout): ALFP-107 add express checkout (#1)"
git push -q origin main
out="$(dry_run)"
expect_contains "$out" "next version: ${TODAY}.1" "first version of the day is .1"
expect_contains "$out" "[ALFP-107](https://acme.atlassian.net/browse/ALFP-107)" "Jira key linked"
expect_contains "$out" "([#1](https://github.com/acme/shop/issues/1))" "PR reference linked"
expect_not_contains "$out" "### Composer Dependencies" "no dependency section without a previous release"

out="$(run_release)"
expect_contains "$out" "Opened release PR for ${TODAY}.1" "release PR opened"
expect_contains "$(git show "origin/calver-release--main:VERSION")" "${TODAY}.1" "release branch has VERSION"

echo "3. Release PR merged"
git checkout -q main
git merge -q --no-ff origin/calver-release--main -m "Merge pull request #2"
git push -q origin main
out="$(FAKE_MERGED="2 $(git rev-parse HEAD)" FAKE_OPEN_PR="" run_release)"
expect_contains "$out" "Released ${TODAY}.1" "merged release PR tagged"
expect_contains "$(cat "$GH_LOG")" "pr edit 2 --remove-label autorelease: pending --add-label autorelease: tagged" "release PR relabelled"
expect_contains "$out" "No releasable changes since ${TODAY}.1" "nothing left to release"

echo "4. Next release: sections and composer changes"
git checkout -q main && git reset -q --hard origin/main
git tag "${TODAY}.1" 2>/dev/null || true
git commit -q --allow-empty -m "fix(catalog)!: drop legacy price indexer"
git commit -q --allow-empty -m "refactor: tidy" -m "BREAKING CHANGE: removed Foo\\Bar service"
git commit -q --allow-empty -m "perf: cache shipping rates"
git commit -q --allow-empty -m "docs: readme"
lock_versions monolog/monolog=3.7.0
jq --indent 4 '.packages += [{"name": "psr/clock", "version": "1.0.0"}] | .packages |= map(select(.name != "psr/log")) | (.["packages-dev"][0].version) = "10.5.38"' \
    composer.lock > composer.lock.tmp && mv composer.lock.tmp composer.lock
git commit -qam "chore(deps): update composer packages"
git push -q origin main
out="$(dry_run)"
expect_contains "$out" "next version: ${TODAY}.2" "counter increments within a day"
expect_contains "$out" "### ⚠ BREAKING CHANGES" "breaking section"
expect_contains "$out" "removed Foo\\Bar service" "BREAKING CHANGE footer used"
expect_contains "$out" "### Bug Fixes" "bug fixes section"
expect_contains "$out" "### Performance Improvements" "performance section"
expect_not_contains "$out" "readme" "docs commit hidden"
expect_contains "$out" "* **monolog/monolog:** 3.5.0 → 3.7.0" "updated package"
expect_contains "$out" "* **phpunit/phpunit (dev):** 10.5.0 → 10.5.38" "updated dev package"
expect_contains "$out" "* **psr/clock:** added 1.0.0" "added package"
expect_contains "$out" "* **psr/log:** removed (was 2.0.0)" "removed package"

echo "5. Stale checkout and conflicting release PR"
out="$(run_release)"   # opens the release PR for .2
stale="$(git rev-parse HEAD~3)"
git checkout -q main && git reset -q --hard origin/main
git commit -q --allow-empty -m "feat: another feature"
git merge -q --no-ff origin/calver-release--main -m "Merge pull request #4"
merge="$(git rev-parse HEAD)"
git push -q origin main
git checkout -q "$stale"
out="$(FAKE_MERGED="4 $merge" FAKE_OPEN_PR="5" run_release)"
expect_contains "$out" "Released ${TODAY}.2" "tags the merged PR despite a stale checkout"
expect_contains "$(cat "$GH_LOG")" "pr close 5 --delete-branch" "closes the leftover release PR"

echo "6. Release PR merged a day after it was prepared"
git checkout -q main && git reset -q --hard origin/main
git tag "${TODAY}.2" "$merge" 2>/dev/null || true
git commit -q --allow-empty -m "feat: late feature"
git push -q origin main
out="$(run_release)"
git checkout -q main && git reset -q --hard origin/main
git merge -q --no-ff origin/calver-release--main -m "Merge pull request #6"
sed -i "s/${TODAY}\.3/${YESTERDAY}.1/g" CHANGELOG.md VERSION
git commit -qam "test: pretend the PR was prepared yesterday"
git push -q origin main
out="$(FAKE_MERGED="6 $(git rev-parse HEAD)" run_release)"
expect_contains "$out" "releasing as ${TODAY}.3 (merge date)" "version moved to the merge date"
expect_contains "$(git log -1 --format=%s origin/main)" "chore(release): release ${TODAY}.3" "fix-up commit pushed"
expect_contains "$(git show origin/main:VERSION)" "${TODAY}.3" "VERSION corrected"
expect_contains "$(git show origin/main:CHANGELOG.md)" "## [${TODAY}.3]" "changelog heading corrected"

echo
if (( FAILED )); then
    echo "${FAILED} check(s) failed"
    exit 1
fi
echo "All checks passed"
