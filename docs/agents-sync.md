# agents-sync.yml

Keeps the **Studioraz organization agent instructions** in every project repo up to
date. The single source is
[`actions/agents-sync/AGENTS.base.md`](../actions/agents-sync/AGENTS.base.md);
change the organization rules there (by PR in ci-templates) and every project gets a
sync PR on its next run.

## What it changes in a project

`AGENTS.md` gets a managed block; everything outside it belongs to the project:

```markdown
<!-- BEGIN ci-templates:agents-base — managed by studioraz/ci-templates, do not edit here -->
# Studioraz organization instructions
…
<!-- END ci-templates:agents-base -->

## Project specifics
…project rules, never touched by the sync…
```

- No `AGENTS.md` yet → created with the block and an empty *Project specifics* section.
- `AGENTS.md` without a block (first run) → block added on top, existing content kept under *Project specifics*.
- Block present → only the block is replaced.
- `CLAUDE.md` → created as `@AGENTS.md`, or the import line is added on top of an existing one (Claude Code reads `CLAUDE.md`; `@AGENTS.md` imports the shared file). Disable with `claude-md: false`.

When something changed, the workflow opens or updates the PR
`chore(agents): sync org agent instructions` from branch `ci-templates/agents-sync`
(a `chore`, so it passes the PR title check and stays out of the changelog). When
nothing changed it closes a leftover sync PR.

## Usage

Copy [`callers/agents-sync.yml`](../callers/agents-sync.yml) — runs Mondays 06:00 UTC
and on demand:

```yaml
on:
  schedule:
    - cron: "0 6 * * 1"
  workflow_dispatch:

permissions:
  contents: write
  pull-requests: write

jobs:
  call-agents-sync:
    uses: studioraz/ci-templates/.github/workflows/agents-sync.yml@master
    secrets:
      token: ${{ secrets.RELEASE_TOKEN }}
```

| Input | Default | Description |
|---|---|---|
| `base-branch` | repository default branch | Branch the PR targets |
| `agents-file` | `AGENTS.md` | Instructions file to manage |
| `claude-md` | `true` | Create/update `CLAUDE.md` so it imports the instructions file |

| Secret | Required | Description |
|---|---|---|
| `token` | no | PAT or GitHub App token. Falls back to `GITHUB_TOKEN`, which does not trigger CI on the sync PR. |

Requires *Allow GitHub Actions to create and approve pull requests* in the repo's
Actions settings.

## Other agents

- **GitHub Copilot** coding agent, Codex, Cursor and others read `AGENTS.md`.
- For a short org-wide subset on github.com, Copilot Business/Enterprise also offers
  organization custom instructions (org settings → Copilot).
