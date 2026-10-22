#!/usr/bin/env bash
#
# Tests for actions/release-please-config/sync.sh. Needs bash, git and jq.
#
# Usage: tests/release-please-config/run.sh

set -euo pipefail

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/actions/release-please-config/sync.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
FAILED=0

pass() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; FAILED=$((FAILED + 1)); }
check() { # description command...
    local description="$1"; shift
    if "$@"; then pass "$description"; else fail "$description"; fi
}
expect_json() { # file jq-filter expected description
    local actual; actual="$(jq -c "$2" "$1")"
    if [[ "$actual" == "$3" ]]; then pass "$4"; else fail "$4 (got $actual, expected $3)"; fi
}

sync() { BASE_FILE="$WORK/base.json" bash "$SCRIPT" > "$WORK/out.txt"; }

cat > "$WORK/base.json" <<'JSON'
{
  "release-type": "php",
  "include-v-in-tag": false,
  "changelog-sections": [{ "type": "feat", "section": "Features" }]
}
JSON

echo "1. Repo without config or manifest"
mkdir "$WORK/new" && cd "$WORK/new" && git init -q
sync
expect_json release-please-config.json '."release-type"' '"php"' "shared keys written"
expect_json release-please-config.json '.packages' '{".":{}}' "root package created"
expect_json .release-please-manifest.json '.' '{".":"0.0.0"}' "manifest starts at 0.0.0"

echo "2. Existing config with project settings"
mkdir "$WORK/existing" && cd "$WORK/existing" && git init -q
cat > release-please-config.json <<'JSON'
{
  "bootstrap-sha": "abc123",
  "include-v-in-tag": true,
  "packages": {
    ".": { "extra-files": ["src/Version.php"], "changelog-sections": [] }
  }
}
JSON
echo '{".": "2.1.1"}' > .release-please-manifest.json
sync
expect_json release-please-config.json '."include-v-in-tag"' 'false' "shared key replaced"
expect_json release-please-config.json '."bootstrap-sha"' '"abc123"' "project top-level key kept"
expect_json release-please-config.json '.packages["."]."extra-files"' '["src/Version.php"]' "package settings kept"
expect_json release-please-config.json 'keys_unsorted | last' '"packages"' "packages listed last"
expect_json .release-please-manifest.json '.' '{".":"2.1.1"}' "existing manifest untouched"
check "warns about package override of a shared key" grep -qF 'sets "changelog-sections"' "$WORK/out.txt"

echo "3. Shared defaults change"
jq '."include-v-in-tag" = true' "$WORK/base.json" > "$WORK/base.tmp" && mv "$WORK/base.tmp" "$WORK/base.json"
sync
expect_json release-please-config.json '."include-v-in-tag"' 'true' "shared key updated"
expect_json release-please-config.json '.packages["."]."extra-files"' '["src/Version.php"]' "package settings still kept"

echo "4. Idempotent"
cp release-please-config.json "$WORK/before.json"
sync
check "config unchanged on re-run" cmp -s release-please-config.json "$WORK/before.json"

echo "5. Manifest from the latest SemVer tag"
mkdir "$WORK/tagged" && cd "$WORK/tagged" && git init -q
git -c user.name=t -c user.email=t@t commit -q --allow-empty -m init
for tag in v1.2.0 1.10.0 1.9.0 2026.10.21.1 v2.0.0-rc.1; do git tag "$tag"; done
sync
expect_json .release-please-manifest.json '.' '{".":"1.10.0"}' "highest X.Y.Z / vX.Y.Z tag used"

echo "6. Several packages without a manifest"
mkdir "$WORK/mono" && cd "$WORK/mono" && git init -q
echo '{"packages": {"a": {}, "b": {}}}' > release-please-config.json
sync
check "manifest not guessed" test ! -e .release-please-manifest.json
check "warns that the manifest is missing" grep -qF '.release-please-manifest.json is missing' "$WORK/out.txt"

echo
if (( FAILED )); then
    echo "${FAILED} check(s) failed"
    exit 1
fi
echo "All checks passed"
