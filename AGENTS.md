# AGENTS.md — CI Templates (studioraz/ci-templates)

## Repository Purpose
A shared library of **reusable GitHub Actions workflows** for Studioraz Magento 2 projects. Consumer repos reference these templates via `workflow_call`; they never run directly in this repo.

---

## Architecture: Two-Layer Design

| Directory | Role |
|-----------|------|
| `.github/workflows/` | **Canonical reusable workflows** — triggered only via `workflow_call`. Must be flat (GitHub does not support subfolders), so names are grouped by prefix (`release-`, `docs-`, `pr-`, …). `_`-prefixed files are this repo's own CI, not reusable. |
| `actions/` | **Composite actions** used by the reusable workflows, one self-contained folder each (they ship their scripts, so no token is needed to fetch them) |
| `callers/` | **Caller templates** — copy these into consumer repos; each is named like the reusable workflow it calls |
| `docs/` | One page per workflow: inputs, secrets, outputs, permissions, setup |
| `tests/` | Script tests, run by `.github/workflows/_ci.yml` |
| `prompts/` | **AI system prompts** — used by documentation workflows (`init-docs`, `update-docs`) |
| `copilot/` | Copilot instruction template for consumer projects (`copilot-instructions-ai.md`). The organization agent instructions moved to `actions/agents-sync/AGENTS.base.md`. |

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

### `release-calver.yml`
Release-please-style releases with CalVer versions `YYYY.MM.DD.N`; keeps a release PR up to date, tags and publishes on merge, `released` output for chaining deploys. Logic in `actions/calver-release/`. Full reference: [docs/release-calver.md](docs/release-calver.md).

### `release-please.yml`
SemVer releases for standalone modules with [release-please](https://github.com/googleapis/release-please): release PR, tag and GitHub Release on merge, `released` output for chaining. The shared config defaults live in `actions/release-please-config/release-please-config.base.json` and reach each module through a sync PR. Full reference: [docs/release-please.md](docs/release-please.md).

### `agents-sync.yml`
Syncs the organization agent instructions (`actions/agents-sync/AGENTS.base.md`) into a managed block of each project's `AGENTS.md` via a weekly PR, and makes `CLAUDE.md` import it. Full reference: [docs/agents-sync.md](docs/agents-sync.md).

### `pr-title.yml`
Requires Conventional Commit PR titles (`amannn/action-semantic-pull-request`); opt-in inputs for scopes, subject pattern, single-commit check, `[WIP]`, ignore labels and an error comment. Full reference: [docs/pr-title.md](docs/pr-title.md).

---

## Key Conventions

- **No `composer install` on update** — `update-composer-package.yml` uses `--no-install` to only refresh `composer.lock`, keeping vendor out of CI for update PRs.
- **Cache keying** — Composer vendor is cached by `hash(composer.lock, composer.json)`; DI generated code by the same key. Cache hits skip the install/compile steps entirely.
- **Caller files pass `php-version` explicitly** — `callers/build-and-deploy.yml` hardcodes `"8.1"`, while `update-composer-package.yml` reads `vars.PHP_VERSION || '8.3'`. Always set `PHP_VERSION` as a GitHub Actions variable in consumer repos.
- **Permissions** — `update-composer-package.yml` requires `contents: write` and `pull-requests: write`; declare these in the caller file.
- **CI** — `.github/workflows/_ci.yml` runs actionlint (pre-existing findings in older workflows are listed in `.github/actionlint.yaml`), shellcheck on `actions/` and `tests/`, and the script tests under `tests/`. Older workflows have no tests — validate them by tracing step IDs and `$GITHUB_OUTPUT` writes.
- **AI prompts centralized** — `prompts/` contains system prompts shared across all consumer repos. Reusable doc workflows check out this repo via sparse checkout to access them at runtime.

---

## Adding a New Reusable Workflow
1. Create `.github/workflows/<group>-<name>.yml` with `on: workflow_call` and typed `inputs`/`secrets`/`outputs`.
2. Put scripts in a composite action under `actions/<name>/` (not inline, not fetched with a token) and reference it as `studioraz/ci-templates/actions/<name>@master`.
3. Create `callers/<group>-<name>.yml` with the triggers and explicit `permissions` a consumer needs.
4. Document it in `docs/<group>-<name>.md` and add a short entry above; add tests under `tests/<name>/` and a job in `_ci.yml`.
5. Never rename or move a reusable workflow consumers already call — keep the old file as a thin wrapper that calls the new one until all consumers are migrated.

