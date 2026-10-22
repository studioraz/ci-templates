# release-please.yml

SemVer releases for **standalone modules** (Composer packages and libraries) with
[release-please](https://github.com/googleapis/release-please). Projects that deploy
use [`release-calver.yml`](release-calver.md) instead.

## How it works

Every run (push to the base branch, weekly schedule, or manual dispatch):

1. **Release** (`googleapis/release-please-action@v4`):
   - Opens or updates the release PR `chore(<branch>): release X.Y.Z` with the version bump
     and a new `CHANGELOG.md` entry.
   - When that PR is merged, tags the merge commit (`X.Y.Z`, no `v`) and publishes a
     GitHub Release.

   The bump comes from Conventional Commit subjects:

   | Commit | Bump | Changelog |
   |---|---|---|
   | `fix:` / `perf:` | patch | Bug Fixes / Performance Improvements |
   | `feat:` | minor | Features |
   | `!` or `BREAKING CHANGE:` footer | major | ⚠ BREAKING CHANGES |
   | `revert:` | patch | Reverts |
   | `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore` | none | hidden |

   Add a `Release-As: X.Y.Z` footer to a commit to force a version.
2. **Sync config** writes the shared defaults into the project's
   `release-please-config.json`. If anything changed, it opens or updates the PR
   `chore(release): sync release-please config` from branch
   `ci-templates/release-please-config-sync`. The PR is a `chore`, so it passes the
   PR title check and stays out of the changelog. When nothing changed, it closes any
   leftover sync PR.

The `released` and `tag-name` outputs carry the version and tag released by the run, to
chain a publish or deploy job.

## Configuration: shared vs project

release-please reads `release-please-config.json` and `.release-please-manifest.json`
from the project's base branch through the GitHub API. They cannot be loaded from this
repo, so the shared part is synced in:

| Where | Owner | Contents |
|---|---|---|
| Top-level keys | **ci-templates**: [`release-please-config.base.json`](../actions/release-please-config/release-please-config.base.json) | `release-type` (`php`), tags without `v` and component, changelog sections |
| Other top-level keys | project | e.g. `bootstrap-sha`, `plugins` |
| `packages` | project | one entry per package path; package keys override the shared top-level ones |
| `.release-please-manifest.json` | release-please | the current version; created by the sync when missing (latest `X.Y.Z`/`vX.Y.Z` tag, or `0.0.0`) |

A typical module config after the sync:

```json
{
  "$schema": "…",
  "release-type": "php",
  "include-v-in-tag": false,
  "include-component-in-tag": false,
  "changelog-sections": [ … ],
  "packages": {
    ".": {
      "extra-files": ["src/Version.php", "README.md"]
    }
  }
}
```

`extra-files` updates the version on lines marked `x-release-please-version`:

```php
public const VERSION = '1.2.3'; // x-release-please-version
```

The sync warns (`::warning::`) when a package sets a shared key, because the package value
then wins over ci-templates. Other release types (`node`, `simple`, …) are set per package:
`"packages": { ".": { "release-type": "node" } }`.

To change the shared defaults for every module, edit the base file here by PR. Each
module gets a sync PR on its next run, which is at least weekly with the caller template.

## Usage

Copy [`callers/release-please.yml`](../callers/release-please.yml):

```yaml
on:
  push:
    branches: [master]
  schedule:
    - cron: "0 6 * * 1"
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  call-release-please:
    uses: studioraz/ci-templates/.github/workflows/release-please.yml@master
    secrets:
      token: ${{ secrets.RELEASE_TOKEN }}
```

| Input | Default | Description |
|---|---|---|
| `target-branch` | repository default branch | Branch releases are cut from |
| `config-file` | `release-please-config.json` | release-please config file |
| `manifest-file` | `.release-please-manifest.json` | release-please manifest file |
| `sync-config` | `true` | Open a sync PR when the config differs from the shared defaults |

| Secret | Required | Description |
|---|---|---|
| `token` | no | PAT or GitHub App token. Falls back to `GITHUB_TOKEN`, which does not trigger CI (e.g. the PR title check) on the release and sync PRs. |

| Output | Description |
|---|---|
| `released` | Version released by this run, empty otherwise |
| `tag-name` | Tag created by this run, empty otherwise |

## Onboarding a module

1. Copy the caller and run it once (*Actions → Release → Run workflow*). The sync PR
   creates `release-please-config.json` and, if missing, the manifest starting at the
   latest tag. Add `extra-files` under `packages["."]` if the module has version
   strings, then merge.
2. Composer modules: leave `version` out of `composer.json`. Packagist reads the version
   from tags, and release-please only updates that field when it exists.
3. Add [`pr-title.yml`](pr-title.md) so every squash commit is a Conventional Commit.

## Repository setup

- *Settings → Actions → General*: **Read and write permissions** and **Allow GitHub
  Actions to create and approve pull requests**.
- Squash-only merging with *Default commit message: Pull request title*.
- A required PR title check never runs on PRs opened with `GITHUB_TOKEN`. Pass a `token`
  (`RELEASE_TOKEN`) or don't make the check required.
