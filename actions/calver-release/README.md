# calver-release (composite action)

Runs `calver-release.sh`, the logic behind the reusable workflow
[`release-calver.yml`](../../.github/workflows/release-calver.yml). Use the
workflow, not this action, from project repos — see
[docs/release-calver.md](../../docs/release-calver.md).

The script ships inside the action so the reusable workflow can run it without a
token to read this private repo.

## Inputs

| Input | Default | Description |
|---|---|---|
| `base-branch` | — (required) | Branch releases are cut from |
| `github-token` | — (required) | Token for git pushes and the GitHub API |
| `timezone` | `Asia/Jerusalem` | Timezone of the release date |
| `jira-base-url` | `""` | Jira site for issue links; empty disables linking |
| `dry-run` | `false` | Print the computed release instead of writing anything |

Output: `released` — the version tagged by this run, empty otherwise.

## Local dry run

Inside a project checkout (bash 4+, GNU coreutils, `git`, `jq`):

```sh
DRY_RUN=1 bash /path/to/ci-templates/actions/calver-release/calver-release.sh
```

## Tests

`tests/calver-release/run.sh` walks through the release lifecycle against a
throwaway repo with a stubbed `gh`; it runs in CI (`.github/workflows/_ci.yml`).
