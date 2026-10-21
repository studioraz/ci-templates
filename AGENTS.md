# AGENTS.md — CI Templates (studioraz/ci-templates)

## Repository Purpose
A shared library of **reusable GitHub Actions workflows** for Studioraz Magento 2 projects. Consumer repos reference these templates via `workflow_call`; they never run directly in this repo.

---

## Architecture: Two-Layer Design

| Directory | Role |
|-----------|------|
| `.github/workflows/` | **Canonical reusable workflows** — triggered only via `workflow_call` |
| `.github/actions/` | **Composite actions** used by the reusable workflows (ship their scripts, so no token is needed to fetch them) |
| `action-caller/` | **Caller templates** — copy these into consumer repos to wire up the reusable workflows |
| `prompts/` | **AI system prompts** — used by documentation workflows (`init-docs`, `update-docs`) |
| `copilot/` | AI/Copilot instruction files for consumer Magento 2 projects (not for this repo itself) |

Consumer repos call templates like:
```yaml
uses: studioraz/ci-templates/.github/workflows/build-and-deploy.yml@master
secrets: inherit
```
The `@master` pin is **intentional** — consumers always get the latest version.

---

## Available Reusable Workflows

### `build-and-deploy.yml`
Builds a Magento 2 app and deploys it via `studioraz/deployer-magento`.
- Inputs: `environment` (staging/production), `php-version` (default `8.3`)
- Steps: Composer install (cached by `composer.lock` hash) → DI compile (cached) → `dep artifact:build localhost` → `dep artifact:deploy <env>`
- Required secret: `SSH_CONNECTION_PRIVATE_KEY`
- Sets `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24: true` globally

### `update-composer-package.yml`
Updates a Composer package and either opens a PR or pushes inplace.
- Inputs: `package` (`vendor/pkg` or `*` for all), `version`, `target` (`pr`|`inplace`), `php-version` (default `8.3`), `with-all-dependencies`, `force-pr`, plus PR metadata overrides
- Optional secret: `token` (PAT; falls back to `GITHUB_TOKEN`)
- PR branch naming: `chore/update-<package>-<version>-<timestamp>` (auto-generated unless overridden)
- Commit/PR title convention: `chore(composer): bump <pkg> from <old> to <new>`
- Auto-detects working directory (`./` then `./src/`) and Composer auth (`./auth.json` or `./src/auth.json`)
- Uses checksum diffing (not `git status`) to detect real changes before committing

### `init-docs.yml`
Generates initial `README.md` and `CHANGELOG.md` for a Magento 2 module using AI inference.
- Trigger: `workflow_call` (no inputs required)
- Steps: Dual checkout (caller repo + ci-templates for prompts) → collect repo context (file tree, signatures, config XML) → AI generates docs → create PR
- Creates branch `docs/init-readme-changelog` with the generated files
- Skips if README already has an "## Overview" section and CHANGELOG has version entries
- System prompt: `prompts/init-docs.md`
- Required permissions: `contents: write`, `models: read`, `pull-requests: write`

### `update-docs.yml`
Updates `README.md` and `CHANGELOG.md` on each release using AI inference.
- Trigger: `workflow_call`
- Inputs: `tag` (required), `url` (optional), `date` (optional, defaults to today)
- Steps: Dual checkout (caller repo + ci-templates for prompts) → diff between previous and current tag → AI generates changelog entry + optional README update → commit directly to master
- CHANGELOG follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/) format; new entries are inserted after `## [Unreleased]`
- System prompt: `prompts/update-docs.md`
- Required permissions: `contents: write`, `models: read`

### `calver-release.yml`
Release-please-style releases with CalVer versions `YYYY.MM.DD.N` (`N` restarts at 1 each day; tags have no `v` prefix).
- Trigger: `workflow_call`; caller runs it on `push` to the base branch + `workflow_dispatch`
- Inputs: `base-branch` (default: repo default branch), `timezone` (default `Asia/Jerusalem`), `jira-base-url` (default `https://studioraz.atlassian.net`, empty disables linking)
- Optional secret: `token` (PAT/App token; falls back to `GITHUB_TOKEN`, which does not trigger CI on the release PR)
- Output: `released` — version tagged by this run, empty otherwise (use it to chain `build-and-deploy.yml`)
- Each run: converts the open release PR to draft (merge lock) → tags + publishes any merged release PR still labelled `autorelease: pending` (moving it to the merge date if it was prepared on an earlier day — pushes a `chore(release)` commit to the base branch) → rebuilds branch `calver-release--<base>` from the latest base branch with `VERSION` + a `CHANGELOG.md` entry and opens/updates the PR → marks the PR ready again (always)
- Changelog: Conventional Commit subjects (`feat`/`fix`/`perf`/`revert`, breaking via `!` or `BREAKING CHANGE:`) + a **Composer Dependencies** section diffed from `composer.lock` since the last tag; Jira keys and `(#123)` become links
- Logic lives in `.github/actions/calver-release/calver-release.sh` (bash 4+, `git`, `gh`, `jq`; `DRY_RUN=1` prints instead of writing)
- Required permissions: `contents: write`, `pull-requests: write`; repo setting *Allow GitHub Actions to create and approve pull requests*

### `pr-title.yml`
Validates that PR titles are Conventional Commits with `amannn/action-semantic-pull-request`.
- Trigger: `workflow_call`; caller runs it on `pull_request` (`opened`, `edited`, `synchronize`, `reopened`)
- Pair with squash-only merging and *Default commit message: Pull request title*, so the validated title is the commit subject `calver-release.yml` reads
- Required permissions: `pull-requests: read`

---

## Key Conventions

- **No `composer install` on update** — `update-composer-package.yml` uses `--no-install` to only refresh `composer.lock`, keeping vendor out of CI for update PRs.
- **Cache keying** — Composer vendor is cached by `hash(composer.lock, composer.json)`; DI generated code by the same key. Cache hits skip the install/compile steps entirely.
- **Caller files pass `php-version` explicitly** — `action-caller/build-and-deploy.yml` hardcodes `"8.1"`, while `update-composer-package.yml` reads `vars.PHP_VERSION || '8.3'`. Always set `PHP_VERSION` as a GitHub Actions variable in consumer repos.
- **Permissions** — `update-composer-package.yml` requires `contents: write` and `pull-requests: write`; declare these in the caller file.
- **No test suite** in this repo — validate changes by tracing input/output step IDs and `$GITHUB_OUTPUT` writes manually.
- **AI prompts centralized** — `prompts/` contains system prompts shared across all consumer repos. Reusable doc workflows check out this repo via sparse checkout to access them at runtime.

---

## Adding a New Reusable Workflow
1. Create `.github/workflows/<name>.yml` with `on: workflow_call` and typed `inputs`/`secrets`.
2. Create a matching `action-caller/<name>.yml` with `on: workflow_dispatch` inputs mirrored from the reusable workflow, calling it with `uses: studioraz/ci-templates/.github/workflows/<name>.yml@master`.
3. Follow the existing pattern: `secrets: inherit` in the caller, explicit `permissions` block where writes are needed.

