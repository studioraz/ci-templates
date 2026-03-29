# AGENTS.md — CI Templates (studioraz/ci-templates)

## Repository Purpose
A shared library of **reusable GitHub Actions workflows** for Studioraz Magento 2 projects. Consumer repos reference these templates via `workflow_call`; they never run directly in this repo.

---

## Architecture: Two-Layer Design

| Directory | Role |
|-----------|------|
| `.github/workflows/` | **Canonical reusable workflows** — triggered only via `workflow_call` |
| `action-caller/` | **Caller templates** — copy these into consumer repos to wire up the reusable workflows |
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

---

## Key Conventions

- **No `composer install` on update** — `update-composer-package.yml` uses `--no-install` to only refresh `composer.lock`, keeping vendor out of CI for update PRs.
- **Cache keying** — Composer vendor is cached by `hash(composer.lock, composer.json)`; DI generated code by the same key. Cache hits skip the install/compile steps entirely.
- **Caller files pass `php-version` explicitly** — `action-caller/build-and-deploy.yml` hardcodes `"8.1"`, while `update-composer-package.yml` reads `vars.PHP_VERSION || '8.3'`. Always set `PHP_VERSION` as a GitHub Actions variable in consumer repos.
- **Permissions** — `update-composer-package.yml` requires `contents: write` and `pull-requests: write`; declare these in the caller file.
- **No test suite** in this repo — validate changes by tracing input/output step IDs and `$GITHUB_OUTPUT` writes manually.

---

## Adding a New Reusable Workflow
1. Create `.github/workflows/<name>.yml` with `on: workflow_call` and typed `inputs`/`secrets`.
2. Create a matching `action-caller/<name>.yml` with `on: workflow_dispatch` inputs mirrored from the reusable workflow, calling it with `uses: studioraz/ci-templates/.github/workflows/<name>.yml@master`.
3. Follow the existing pattern: `secrets: inherit` in the caller, explicit `permissions` block where writes are needed.

