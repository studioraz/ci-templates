#!/usr/bin/env bash
#
# CalVer (YYYY.MM.DD.N) release automation modelled on release-please.
#
# PR mode:      collects Conventional Commits and composer.lock changes since the
#               last release tag and keeps a release PR open with the next version,
#               updated VERSION and CHANGELOG.md.
# Release mode: when that PR is merged, tags its merge commit and publishes a
#               GitHub Release with the matching CHANGELOG section. If the PR was
#               prepared on an earlier day, the version is moved to the merge date
#               first (commit pushed to the base branch).
#
# Env: GH_TOKEN (required unless DRY_RUN=1), BASE_BRANCH (default: main),
#      TZ for the release date (default: system timezone),
#      JIRA_BASE_URL to link issue keys such as ALFP-107 (e.g. https://acme.atlassian.net),
#      DRY_RUN=1 to print the computed release without pushing or calling the API.

set -euo pipefail

DRY_RUN="${DRY_RUN:-0}"
BASE_BRANCH="${BASE_BRANCH:-main}"
RELEASE_BRANCH="calver-release--${BASE_BRANCH}"
LABEL_PENDING="autorelease: pending"
LABEL_TAGGED="autorelease: tagged"
TAG_PATTERN='^[0-9]{4}\.[0-9]{2}\.[0-9]{2}\.[0-9]+$'
# Also counts date-only tags (YYYY.MM.DD) made before adopting this workflow as
# previous releases, so the first release PR starts from the last of them.
PREVIOUS_TAG_PATTERN='^[0-9]{4}\.[0-9]{2}\.[0-9]{2}(\.[0-9]+)?$'
RELEASE_SUBJECT_PREFIX="chore(release): release "

if [[ -z "${GITHUB_REPOSITORY:-}" ]]; then
    GITHUB_REPOSITORY="$(git remote get-url origin | sed -E 's#(\.git)?$##; s#^.*[:/]([^/]+/[^/]+)$#\1#')"
fi
REPO_URL="${GITHUB_SERVER_URL:-https://github.com}/${GITHUB_REPOSITORY}"

log() { echo "::notice::$*" >&2; }

is_dry_run() { [[ "$DRY_RUN" == "1" ]]; }

today() { date +%Y.%m.%d; }

git_identity() {
    git config user.name "github-actions[bot]"
    git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
}

# --------------------------------------------------------------------------
# Release mode
# --------------------------------------------------------------------------

# Merged release PRs still labelled pending, as "<number> <merge sha>" lines.
# Looked up via the API rather than from HEAD, so a delayed or re-run workflow
# still finds them.
pending_release_prs() {
    if is_dry_run; then
        if [[ "$(git log -1 --format=%s)" == "$RELEASE_SUBJECT_PREFIX"* ]]; then
            echo "- $(git rev-parse HEAD)"
        fi
        return 0
    fi
    gh pr list --base "$BASE_BRANCH" --state merged --label "$LABEL_PENDING" \
        --json number,mergeCommit --jq 'sort_by(.number)[] | "\(.number) \(.mergeCommit.oid)"'
}

# CHANGELOG section body (without its heading) for version $1, read from stdin.
release_notes() {
    awk -v heading="## [$1]" '
        /^## / { if (found) exit; if (index($0, heading) == 1) { found = 1; next } }
        found && (started || NF) { started = 1; print }
    '
}

mark_tagged() {
    local pr="$1"
    [[ "$pr" != "-" ]] || return 0
    gh label create "$LABEL_TAGGED" --color 0E8A16 --description "Release PR has been tagged" --force >/dev/null
    gh pr edit "$pr" --remove-label "$LABEL_PENDING" --add-label "$LABEL_TAGGED" >/dev/null
}

# Moves the prepared release from version $1 to $2 in VERSION and CHANGELOG.md.
retarget_release() {
    local planned="$1" version="$2" planned_re="${1//./\\.}"
    echo "$version" > VERSION
    sed -i -E "/^## \[${planned_re}\]/{ s/${planned_re}/${version}/g; s/\([0-9]{4}-[0-9]{2}-[0-9]{2}\)$/($(date +%F))/ }" CHANGELOG.md
}

# Tags and publishes the release prepared by PR $1, merged as commit $2.
release() {
    local pr="$1" target="$2" planned version
    planned="$(git show "${target}:VERSION" | tr -d '[:space:]')"
    if ! [[ "$planned" =~ $TAG_PATTERN ]]; then
        echo "VERSION at ${target} contains '$planned', which is not a CalVer version" >&2
        exit 1
    fi
    if git rev-parse -q --verify "refs/tags/${planned}" >/dev/null; then
        log "Tag ${planned} already exists"
        is_dry_run || mark_tagged "$pr"
        return 0
    fi

    version="$planned"
    if [[ "${planned%.*}" != "$(today)" ]]; then
        # Applied on top of the current base branch tip, which contains the merge.
        version="$(next_version)"
        log "Release PR was prepared as ${planned}; releasing as ${version} (merge date)"
        retarget_release "$planned" "$version"
        if ! is_dry_run; then
            git_identity
            git commit -q -am "${RELEASE_SUBJECT_PREFIX}${version}"
            git push origin "HEAD:${BASE_BRANCH}"
        fi
        target="$(git rev-parse HEAD)"
    fi

    if is_dry_run; then
        log "[dry-run] would tag ${target:0:7} as ${version} and publish release:"
        git show "${target}:CHANGELOG.md" | release_notes "$version"
        return 0
    fi

    gh release create "$version" \
        --target "$target" \
        --title "$version" \
        --notes "$(git show "${target}:CHANGELOG.md" | release_notes "$version")"
    git tag "$version" "$target"
    log "Released ${version}"
    if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
        echo "released=${version}" >> "$GITHUB_OUTPUT"
    fi

    mark_tagged "$pr"
}

# --------------------------------------------------------------------------
# PR mode
# --------------------------------------------------------------------------

last_release_tag() {
    git tag --merged HEAD | grep -E "$PREVIOUS_TAG_PATTERN" | sort -V | tail -n 1 || true
}

next_version() {
    local day last_n
    day="$(today)"
    last_n="$(git tag --list "${day}.*" | grep -E "$TAG_PATTERN" | sed "s/^${day}\.//" | sort -n | tail -n 1 || true)"
    echo "${day}.$(( ${last_n:-0} + 1 ))"
}

# Turns "(#123)" and Jira keys such as "ALFP-107" into links.
link_refs() {
    local jira=""
    if [[ -n "${JIRA_BASE_URL:-}" ]]; then
        jira="s#(^|[^A-Za-z0-9/[-])([A-Z][A-Z0-9]+-[0-9]+)#\\1[\\2](${JIRA_BASE_URL%/}/browse/\\2)#g"
    fi
    sed -E -e "s#\\(\\#([0-9]+)\\)#([\\#\\1](${REPO_URL}/issues/\\1))#g" ${jira:+-e "$jira"}
}

# Fills the BREAKING/FEATURES/FIXES/PERF/REVERTS bullet lists from commits in $1.
collect_commits() {
    local range="$1" record sha subject body type scope bang desc bullet breaking_note
    local re='^([a-zA-Z]+)(\(([^)]*)\))?(!)?: (.+)$'

    while IFS= read -r -d $'\x1e' record; do
        record="${record#$'\n'}"
        sha="${record%%$'\x1f'*}"
        record="${record#*$'\x1f'}"
        subject="${record%%$'\x1f'*}"
        body="${record#*$'\x1f'}"

        [[ "$subject" == "$RELEASE_SUBJECT_PREFIX"* ]] && continue
        [[ "$subject" =~ $re ]] || continue

        type="${BASH_REMATCH[1],,}"
        scope="${BASH_REMATCH[3]}"
        bang="${BASH_REMATCH[4]}"
        desc="${BASH_REMATCH[5]}"

        bullet="* ${scope:+**${scope}:** }${desc} ([${sha:0:7}](${REPO_URL}/commit/${sha}))"
        bullet="$(link_refs <<< "$bullet")"

        case "$type" in
            feat)   FEATURES+=("$bullet") ;;
            fix)    FIXES+=("$bullet") ;;
            perf)   PERF+=("$bullet") ;;
            revert) REVERTS+=("$bullet") ;;
        esac

        breaking_note="$(grep -m1 -E '^BREAKING[ -]CHANGE: ' <<< "$body" | sed -E 's/^BREAKING[ -]CHANGE: //' || true)"
        if [[ -n "$bang" || -n "$breaking_note" ]]; then
            BREAKING+=("$(link_refs <<< "* ${scope:+**${scope}:** }${breaking_note:-$desc} ([${sha:0:7}](${REPO_URL}/commit/${sha}))")")
        fi
    done < <(git log --no-merges --format='%H%x1f%s%x1f%b%x1e' "$range")
}

# Fills DEPENDENCIES with composer packages updated/added/removed since tag $1.
collect_dependencies() {
    local tag="$1" old_lock deps
    [[ -f composer.lock ]] || return 0
    # The first release has no baseline to diff against.
    [[ -n "$tag" ]] || return 0

    old_lock="$(mktemp)"
    git show "${tag}:composer.lock" > "$old_lock" 2>/dev/null || echo '{}' > "$old_lock"

    deps="$(jq -rn --slurpfile old "$old_lock" --slurpfile new composer.lock '
        def pkgs:
            ([(.packages // [])[] | {key: .name, value: {v: .version, dev: false}}]
             + [(.["packages-dev"] // [])[] | {key: .name, value: {v: .version, dev: true}}])
            | from_entries;
        def pkg_label($p): "**\($p.key)\(if $p.value.dev then " (dev)" else "" end):**";
        ($old[0] | pkgs) as $o | ($new[0] | pkgs) as $n
        | ($n | to_entries | sort_by(.key)) as $ne
        | ($o | to_entries | sort_by(.key)) as $oe
        | ($ne[] | select($o[.key] != null and $o[.key].v != .value.v)
            | "* \(pkg_label(.)) \($o[.key].v) → \(.value.v)"),
          ($ne[] | select($o[.key] == null)
            | "* \(pkg_label(.)) added \(.value.v)"),
          ($oe[] | select($n[.key] == null)
            | "* \(pkg_label(.)) removed (was \(.value.v))")
    ')"
    rm -f "$old_lock"
    [[ -z "$deps" ]] || mapfile -t DEPENDENCIES <<< "$deps"
}

append_section() {
    local title="$1"; shift
    (( $# )) || return 0
    printf '\n### %s\n\n' "$title"
    printf '%s\n' "$@"
}

build_entry() {
    local version="$1" previous="$2"
    if [[ -n "$previous" ]]; then
        printf '## [%s](%s/compare/%s...%s) (%s)\n' "$version" "$REPO_URL" "$previous" "$version" "$(date +%F)"
    else
        printf '## [%s](%s/commits/%s) (%s)\n' "$version" "$REPO_URL" "$version" "$(date +%F)"
    fi
    append_section "⚠ BREAKING CHANGES" "${BREAKING[@]}"
    append_section "Features" "${FEATURES[@]}"
    append_section "Bug Fixes" "${FIXES[@]}"
    append_section "Performance Improvements" "${PERF[@]}"
    append_section "Reverts" "${REVERTS[@]}"
    append_section "Composer Dependencies" "${DEPENDENCIES[@]}"
}

build_pr_body() {
    local version="$1" entry="$2"
    cat <<EOF
:robot: I have created a release *beep* *boop*
---


${entry}

---
This PR was generated by the CalVer release workflow. Merging it will tag \`${version}\` and publish a GitHub Release.
EOF
}

prepend_changelog() {
    local entry="$1" tmp
    [[ -f CHANGELOG.md ]] || printf '# Changelog\n' > CHANGELOG.md
    tmp="$(mktemp)"
    { head -n 1 CHANGELOG.md; echo; printf '%s\n' "$entry"; tail -n +2 CHANGELOG.md; } > "$tmp"
    mv "$tmp" CHANGELOG.md
}

open_or_update_pr() {
    local version="$1" body_file="$2" title="${RELEASE_SUBJECT_PREFIX}$1" pr

    git_identity
    git checkout -B "$RELEASE_BRANCH"
    echo "$version" > VERSION
    prepend_changelog "$ENTRY"
    git add VERSION CHANGELOG.md
    git commit -q -m "$title"

    if git rev-parse -q --verify "refs/remotes/origin/${RELEASE_BRANCH}" >/dev/null \
        && git diff --quiet "origin/${RELEASE_BRANCH}" HEAD; then
        log "Release branch already up to date"
    else
        git push --force origin "$RELEASE_BRANCH"
    fi

    gh label create "$LABEL_PENDING" --color FBCA04 --description "Release PR not yet tagged" --force >/dev/null

    pr="$(open_release_pr)"
    if [[ -n "$pr" ]]; then
        gh pr edit "$pr" --title "$title" --body-file "$body_file" --add-label "$LABEL_PENDING" >/dev/null
        log "Updated release PR #${pr} for ${version}"
    else
        gh pr create --base "$BASE_BRANCH" --head "$RELEASE_BRANCH" \
            --title "$title" --body-file "$body_file" --label "$LABEL_PENDING"
        log "Opened release PR for ${version}"
    fi
}

open_release_pr() {
    gh pr list --head "$RELEASE_BRANCH" --base "$BASE_BRANCH" --state open --json number --jq '.[0].number // empty'
}

# Always work from the latest base branch tip, not the commit that triggered the
# run: events can arrive late, and a stale base makes the release PR conflict.
sync_base_branch() {
    git fetch -q --force --tags origin "+refs/heads/*:refs/remotes/origin/*"
    git checkout -q -B "$BASE_BRANCH" "origin/${BASE_BRANCH}"
}

main() {
    local pending pr sha previous range version body_file

    is_dry_run || sync_base_branch

    pending="$(pending_release_prs)"
    while read -r pr sha; do
        [[ -n "$sha" ]] && release "$pr" "$sha" < /dev/null
    done <<< "$pending"

    BREAKING=() FEATURES=() FIXES=() PERF=() REVERTS=() DEPENDENCIES=()

    previous="$(last_release_tag)"
    range="${previous:+${previous}..}HEAD"
    collect_commits "$range"
    collect_dependencies "$previous"

    if (( ${#BREAKING[@]} + ${#FEATURES[@]} + ${#FIXES[@]} + ${#PERF[@]} + ${#REVERTS[@]} + ${#DEPENDENCIES[@]} == 0 )); then
        log "No releasable changes since ${previous:-the beginning of history}"
        if ! is_dry_run && pr="$(open_release_pr)" && [[ -n "$pr" ]]; then
            gh pr close "$pr" --delete-branch --comment "Closing: no releasable changes since ${previous}." >/dev/null
            log "Closed stale release PR #${pr}"
        fi
        return 0
    fi

    version="$(next_version)"
    ENTRY="$(build_entry "$version" "$previous")"
    body_file="$(mktemp)"
    build_pr_body "$version" "$ENTRY" > "$body_file"

    if is_dry_run; then
        log "[dry-run] next version: ${version} (previous: ${previous:-none})"
        cat "$body_file"
        return 0
    fi

    open_or_update_pr "$version" "$body_file"
}

main "$@"
