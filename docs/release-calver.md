# release-calver.yml

Release-please-style releases with CalVer versions **`YYYY.MM.DD.N`** — `N`
restarts at 1 every day, tags have no `v` prefix (e.g. `2026.10.21.1`).

## How it works

Every run (push to the base branch, or manual dispatch):

1. **Lock** — converts the open release PR to a draft so it can't be merged mid-update.
2. **Release** — for each merged release PR still labelled `autorelease: pending`:
   tags its merge commit, publishes a GitHub Release with the changelog entry and
   relabels it `autorelease: tagged`. If the PR was prepared on an earlier day it
   first pushes a `chore(release): release <today's version>` commit to the base
   branch, so the version is the merge date.
3. **Release PR** — collects changes since the last tag and force-pushes branch
   `calver-release--<base>` (built from the latest base branch) with `VERSION` and a
   new `CHANGELOG.md` entry, then opens or updates `chore(release): release <version>`.
   Closes it if nothing is left to release.
4. **Unlock** — marks the PR ready again (always, also when the run fails).

The `released` output carries the version tagged by the run, to chain a deploy.

## Changelog

- Conventional Commit subjects: `feat` → Features, `fix` → Bug Fixes,
  `perf` → Performance Improvements, `revert` → Reverts, `!` or a
  `BREAKING CHANGE:` footer → ⚠ BREAKING CHANGES. Other types are not listed.
- **Composer Dependencies** — every package updated, added or removed in
  `composer.lock` since the last release (dev packages marked `(dev)`).
- Jira keys (`ALFP-107`) link to `<jira-base-url>/browse/<KEY>`; `(#123)` links to the PR.

## Usage

Copy [`callers/release-calver.yml`](../callers/release-calver.yml):

```yaml
on:
  push:
    branches: [master]
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  call-release-calver:
    uses: studioraz/ci-templates/.github/workflows/release-calver.yml@master
    secrets:
      token: ${{ secrets.RELEASE_TOKEN }}
```

| Input | Default | Description |
|---|---|---|
| `base-branch` | repository default branch | Branch releases are cut from |
| `timezone` | `Asia/Jerusalem` | Timezone of the release date |
| `jira-base-url` | `https://studioraz.atlassian.net` | Jira site; empty disables linking |

| Secret | Required | Description |
|---|---|---|
| `token` | no | PAT or GitHub App token. Falls back to `GITHUB_TOKEN`, which does not trigger CI on the release PR. |

| Output | Description |
|---|---|
| `released` | Version tagged by this run, empty otherwise |

## Repository setup

- *Settings → Actions → General*: **Read and write permissions** and **Allow GitHub
  Actions to create and approve pull requests**.
- Recommended: squash-only merging with *Default commit message: Pull request title*,
  plus [`pr-title.yml`](pr-title.md) so every title is a Conventional Commit.
- If the base branch is protected, let the token's actor bypass it — the merge-date
  correction pushes to the base branch.

Implementation: [`actions/calver-release`](../actions/calver-release/README.md).
