#!/usr/bin/env bash
#
# Writes the shared release-please defaults (release-please-config.base.json) into
# the project's release-please config, leaving project settings alone.
#
# - Top-level keys of the base file are set in the project config (shared, managed here).
# - Other top-level keys and everything under "packages" belong to the project and are kept.
#   release-please applies top-level keys to every package unless the package sets them.
# - No config yet:   created from the base file with one root package ".".
# - No manifest yet: created for the root package with the latest SemVer tag
#                    (X.Y.Z or vX.Y.Z), or 0.0.0 when there is none.
# - Warns when a package sets a shared key, because the package value wins.
#
# Env: CONFIG_FILE (default release-please-config.json), MANIFEST_FILE (default
#      .release-please-manifest.json), BASE_FILE (default: release-please-config.base.json
#      next to this script).

set -euo pipefail

CONFIG_FILE="${CONFIG_FILE:-release-please-config.json}"
MANIFEST_FILE="${MANIFEST_FILE:-.release-please-manifest.json}"
BASE_FILE="${BASE_FILE:-$(dirname "${BASH_SOURCE[0]}")/release-please-config.base.json}"

tmp="$(mktemp)"
# Shared keys first, then project keys, then "packages".
{ if [[ -f "$CONFIG_FILE" ]]; then cat "$CONFIG_FILE"; else echo '{}'; fi; } |
jq --slurpfile base "$BASE_FILE" '
    $base[0] as $b
    | ($b + with_entries(select(.key as $k | $b | has($k) | not))) as $merged
    | ($merged | del(.packages)) + {packages: ($merged.packages // {".": {}})}
' > "$tmp"
mv "$tmp" "$CONFIG_FILE"

jq -r --slurpfile base "$BASE_FILE" '
    .packages | to_entries[] | .key as $path
    | .value | keys[] | select(. as $k | $base[0] | has($k))
    | "\($path)\t\(.)"
' "$CONFIG_FILE" | while IFS=$'\t' read -r path key; do
    echo "::warning file=${CONFIG_FILE}::Package \"${path}\" sets \"${key}\", which overrides the shared value from ci-templates"
done

if [[ ! -f "$MANIFEST_FILE" ]]; then
    if [[ "$(jq -c '.packages | keys' "$CONFIG_FILE")" == '["."]' ]]; then
        version="$(git tag --list 2>/dev/null | grep -E '^v?[0-9]+\.[0-9]+\.[0-9]+$' | sed 's/^v//' | sort -V | tail -n 1 || true)"
        jq -n --arg v "${version:-0.0.0}" '{".": $v}' > "$MANIFEST_FILE"
    else
        echo "::warning file=${CONFIG_FILE}::${MANIFEST_FILE} is missing; create it with the current version of each package"
    fi
fi
