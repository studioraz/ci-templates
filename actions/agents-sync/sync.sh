#!/usr/bin/env bash
#
# Writes the organization agent instructions (AGENTS.base.md) into a managed
# block of the project's AGENTS.md, leaving everything outside the block alone.
#
# - No AGENTS.md:          creates it with the block and an empty "Project specifics" section.
# - AGENTS.md with block:  replaces the block.
# - AGENTS.md without:     puts the block on top and keeps the existing content
#                          under "Project specifics".
# - CLAUDE.md (optional):  makes sure it imports AGENTS.md (Claude Code reads CLAUDE.md).
#
# Env: AGENTS_FILE (default AGENTS.md), BASE_FILE (default: AGENTS.base.md next to
#      this script), CLAUDE_MD=true|false (default true).

set -euo pipefail

AGENTS_FILE="${AGENTS_FILE:-AGENTS.md}"
BASE_FILE="${BASE_FILE:-$(dirname "${BASH_SOURCE[0]}")/AGENTS.base.md}"
CLAUDE_MD="${CLAUDE_MD:-true}"
BEGIN="<!-- BEGIN ci-templates:agents-base — managed by studioraz/ci-templates, do not edit here -->"
END="<!-- END ci-templates:agents-base -->"

block() {
    printf '%s\n\n' "$BEGIN"
    cat "$BASE_FILE"
    printf '\n%s\n' "$END"
}

tmp="$(mktemp)"
if [[ ! -f "$AGENTS_FILE" ]]; then
    { block; printf '\n## Project specifics\n\n<!-- Add instructions specific to this project below. -->\n'; } > "$tmp"
elif grep -qF -- "${BEGIN%% —*}" "$AGENTS_FILE" && grep -qF -- "$END" "$AGENTS_FILE"; then
    # Keep everything before BEGIN and after END, swap the block in between.
    awk -v begin="${BEGIN%% —*}" -v end="$END" -v blockfile=<(block) '
        index($0, begin) == 1 { while ((getline line < blockfile) > 0) print line; skipping = 1; next }
        skipping && index($0, end) == 1 { skipping = 0; next }
        !skipping { print }
    ' "$AGENTS_FILE" > "$tmp"
else
    { block; printf '\n## Project specifics\n\n'; cat "$AGENTS_FILE"; } > "$tmp"
fi
mv "$tmp" "$AGENTS_FILE"

if [[ "$CLAUDE_MD" == "true" ]]; then
    import="@${AGENTS_FILE}"
    if [[ ! -f CLAUDE.md ]]; then
        printf '%s\n' "$import" > CLAUDE.md
    elif ! grep -qxF -- "$import" CLAUDE.md; then
        { printf '%s\n\n' "$import"; cat CLAUDE.md; } > "$tmp" && mv "$tmp" CLAUDE.md
    fi
fi
