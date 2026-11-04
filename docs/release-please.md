# release-please.yml

SemVer releases for **standalone modules** (Composer packages and libraries) with
[release-please](https://github.com/googleapis/release-please). Projects that deploy
use [`release-calver.yml`](release-calver.md) instead.

## How it works

Every run (push to the base branch, weekly schedule, or manual dispatch):

1. **Release** (`googleapis/release-please-action@v4`):
   - Opens or updates the release PR `chore(<branch>): release X.Y.Z` with the version bump
     and a new `CHANGELOG.md` entry.
   - When that PR is merged, tags the merge commit and publishes a GitHub Release, both named
     `X.Y.Z` with no `v` prefix (the org version convention).

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
| Top-level keys | **ci-templates**: [`release-please-config.base.json`](../actions/release-please-config/release-please-config.base.json) | `release-type` (`php`), tags and release names without `v` or component, changelog sections |
| Other top-level keys | project | e.g. `bootstrap-sha`, `plugins` |
| `packages` | project | one entry per package path; package keys override the shared top-level ones |
| `.release-please-manifest.json` | release-please | the current version; created by the sync when missing (latest `X.Y.Z`/`vX.Y.Z` tag, or `0.0.0`) |

A typical module config after the sync:

```json
{
  "$schema": "…",
  "release-type": "php",
  "include-v-in-tag": false,
  "include-v-in-release-name": false,
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

1. Preseed the caller, shared config with `packages["."]`, and manifest together.
   Do not run the release job before its config exists. Use the enrollment tool below,
   or copy the shared base config and verify a release-branch baseline manually.
   Add `extra-files` under `packages["."]` if the module has version strings.
2. Composer modules: leave `version` out of `composer.json`. Packagist reads the version
   from tags, and release-please only updates that field when it exists.
3. Add [`pr-title.yml`](pr-title.md) so every squash commit is a Conventional Commit.

## Repository setup

- *Settings → Actions → General*: **Read and write permissions** and **Allow GitHub
  Actions to create and approve pull requests**.
- Squash-only merging with *Default commit title: Pull request title* (`PR_TITLE`)
  and *Default commit message: Pull request body* (`PR_BODY`), preserving release footers.
- A required PR title check never runs on PRs opened with `GITHUB_TOKEN`. Pass a `token`
  (`RELEASE_TOKEN`) or don't make the check required.

## Enrollment tooling

Requires Python 3.9+, Git, and authenticated `gh` with repository/workflow access.
The Python implementation uses only the standard library, including numeric SemVer
comparison and JSON merging; no YAML rewriting or extra runtime packages are needed.
It operates exclusively in automatically cleaned temporary clones, never a developer's checkout.

```sh
# Explicit selection bypasses activity filtering, never fork/archive/disabled exclusions.
python3 scripts/enroll-release-please.py \
  --repo studioraz/magento2-product-attribute-option-sorting \
  --report /tmp/release-please-pilot.json

# Read-only inventory and full per-target dry runs; refreshes GitHub metadata.
python3 scripts/enroll-release-please.py --discover --report /tmp/release-please-inventory.json

# Only after reviewing the dry run: pushes a stable owned branch and opens a DRAFT PR.
python3 scripts/enroll-release-please.py \
  --repo studioraz/magento2-product-attribute-option-sorting \
  --apply --report /tmp/release-please-applied.json

# Untagged module only: explicit one-time first-release intent.
python3 scripts/enroll-release-please.py --repo studioraz/magento2-new-module \
  --initial-version 1.0.0 --report /tmp/release-please-new.json
```

Default is **dry run**. `--discover` enumerates `studioraz/magento2-*` repositories
pushed within 365 days, excluding forks, archived and disabled repositories.
Composer type must be `magento2-module`; template/demo/example/test repositories and packages are
excluded. Other ambiguous projects are blocked rather than guessed. Bulk application
requires explicit `--discover --apply`; do not run it before pilot review.

The JSON report includes each status, changed-file statistics and full patch,
baseline evidence, Actions policies, branch protection/rulesets (including tag rules),
merge-settings prerequisites and token uncertainty. The local shared base must match
the published `@master` version before enrollment. Nonzero exit means at least one
target/API operation was blocked; other targets are still reported. Inspect the reason,
not just the aggregate exit code. API/auth errors are not interpreted as missing settings.
Organization secret metadata is deliberately not queried: permission to list secrets
does not prove an effective token or its scopes. No secret values are requested.

Baseline selection uses the numerically highest stable `X.Y.Z`/`vX.Y.Z` tag verified
reachable from the actual default/release branch, cross-checked against published
stable releases. Divergent tags, prereleases, nonstandard release history and stale
manifests block automatic migration. Composer's version and tag dates are not baselines.
Existing manifests and project-owned config/package settings are preserved.
Repositories with an existing shared release caller and root config/manifest are
reported as already enrolled and left untouched, not certified anew against all
current onboarding conventions.
Untagged modules require `--initial-version`; their manifest starts at `0.0.0` and
the requested `Release-As` appears once in both enrollment commit and PR body.
It is never a permanent config override.

Explicit Composer `version` is removed only after a tracked-consumer scan; potential
consumers or a lockfile block automatic removal for manual review. Magento setup versions
and installation examples are untouched. Existing differing workflows or Releases
sections, multi-package configs, version overrides, and competing release publishers
also require manual integration rather than blind replacement.

The stable branch is `ci-templates/release-please-enrollment`, with PR/commit title
`ci: configure release please`. Reruns recognize unchanged owned draft PRs and do not
create duplicates. Updates require this operator's tool-marked commits and PR, only
enrollment paths, and an unchanged base; updates are fast-forward pushes, never force
pushes. Existing PR bodies/review notes are not rewritten; bootstrap footers must
match the requested intent. Unowned branches, ready PRs, concurrent edits and moved bases block updates.

The tool **never changes repository settings**, merges a PR or dispatches a release.
Drafts carry explicit merge blockers: approve squash-only `PR_TITLE`/`PR_BODY`,
Actions write/create-PR permissions, private shared-workflow access and allowed-actions
policies, required-check/bypass and tag-protection rules. When effective `RELEASE_TOKEN`
is unknown, do not require bot PR CI that `GITHUB_TOKEN` cannot trigger.
**Public repositories cannot call workflows in private `ci-templates`, even with
organization access or a PAT.** Such targets are reported as blocked, and `--apply`
refuses any branch/PR writes. Resolving this requires an explicitly approved public
shared-workflow distribution (including its composite actions), or a separately
approved caller visibility change; this tool does neither. See GitHub's
[reusable workflow access table](https://docs.github.com/en/actions/reference/workflows-and-actions/reusing-workflow-configurations#access-to-reusable-workflows).
PR creation and static validation are not live workflow proof: review prerequisites,
merge the pilot deliberately, then observe release/config-sync and PR-title runs before
bulk enrollment. Do not trigger an artificial release just to test onboarding.
