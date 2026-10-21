#!/usr/bin/env bash
#
# Tests for actions/agents-sync/sync.sh. Needs bash and coreutils.
#
# Usage: tests/agents-sync/run.sh

set -euo pipefail

SCRIPT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/actions/agents-sync/sync.sh"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
FAILED=0

pass() { echo "  ✓ $1"; }
fail() { echo "  ✗ $1"; FAILED=$((FAILED + 1)); }
expect_contains() { if grep -qF -- "$2" "$1"; then pass "$3"; else fail "$3 (missing: $2)"; fi; }
expect_not_contains() { if grep -qF -- "$2" "$1"; then fail "$3 (unexpected: $2)"; else pass "$3"; fi; }
check() { # description command...
    local description="$1"; shift
    if "$@"; then pass "$description"; else fail "$description"; fi
}
expect_count() { # file needle count description
    local n; n="$(grep -cF -- "$2" "$1" || true)"
    if [[ "$n" == "$3" ]]; then pass "$4"; else fail "$4 (found $n, expected $3)"; fi
}

sync() { BASE_FILE="$WORK/base.md" bash "$SCRIPT"; }

printf '# Org rules\n\n- rule one\n' > "$WORK/base.md"

echo "1. Repo without AGENTS.md"
mkdir "$WORK/new" && cd "$WORK/new"
sync
expect_contains AGENTS.md "<!-- BEGIN ci-templates:agents-base" "managed block created"
expect_contains AGENTS.md "- rule one" "org rules written"
expect_contains AGENTS.md "## Project specifics" "project section created"
expect_contains CLAUDE.md "@AGENTS.md" "CLAUDE.md imports AGENTS.md"

echo "2. Existing AGENTS.md without a block"
mkdir "$WORK/existing" && cd "$WORK/existing"
cat > AGENTS.md <<'MD'
# My shop

- use store code `il`
MD
printf 'Prefer short answers.\n' > CLAUDE.md
sync
expect_contains AGENTS.md "- rule one" "org rules added"
expect_contains AGENTS.md "- use store code \`il\`" "existing content kept"
check "org block placed above existing content" \
    test "$(grep -n 'rule one' AGENTS.md | cut -d: -f1)" -lt "$(grep -n 'store code' AGENTS.md | cut -d: -f1)"
expect_contains CLAUDE.md "@AGENTS.md" "import added to existing CLAUDE.md"
expect_contains CLAUDE.md "Prefer short answers." "existing CLAUDE.md content kept"

echo "3. Org rules change"
printf '# Org rules\n\n- rule two\n' > "$WORK/base.md"
sync
expect_contains AGENTS.md "- rule two" "block updated"
expect_not_contains AGENTS.md "- rule one" "old rules removed"
expect_contains AGENTS.md "- use store code \`il\`" "project content untouched"
expect_count AGENTS.md "<!-- BEGIN ci-templates:agents-base" 1 "still exactly one block"
expect_count AGENTS.md "## Project specifics" 1 "still exactly one project section"

echo "4. Idempotent"
cp AGENTS.md "$WORK/before.md"; cp CLAUDE.md "$WORK/before-claude.md"
sync
check "AGENTS.md unchanged on re-run" cmp -s AGENTS.md "$WORK/before.md"
check "CLAUDE.md unchanged on re-run" cmp -s CLAUDE.md "$WORK/before-claude.md"

echo "5. CLAUDE_MD=false"
mkdir "$WORK/no-claude" && cd "$WORK/no-claude"
CLAUDE_MD=false sync
check "CLAUDE.md not created" test ! -e CLAUDE.md

echo
if (( FAILED )); then
    echo "${FAILED} check(s) failed"
    exit 1
fi
echo "All checks passed"
