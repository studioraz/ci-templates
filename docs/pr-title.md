# pr-title.yml

Fails a PR whose title is not a [Conventional Commit](https://www.conventionalcommits.org/),
using [`amannn/action-semantic-pull-request`](https://github.com/amannn/action-semantic-pull-request).
With squash merging the PR title becomes the commit subject that
[`release-calver.yml`](release-calver.md) and [`release-please.yml`](release-please.md)
turn into a changelog entry.

Allowed types by default: `feat`, `fix`, `perf`, `revert`, `docs`, `style`, `refactor`,
`test`, `build`, `ci`, `chore`. Recommended form:

```
type(scope): JIRA-KEY description      e.g. feat(checkout): ALFP-107 add express checkout
```

## Usage

Copy [`callers/pr-title.yml`](../callers/pr-title.yml):

```yaml
on:
  pull_request:
    types: [opened, edited, synchronize, reopened]

permissions:
  pull-requests: read

jobs:
  call-pr-title:
    uses: studioraz/ci-templates/.github/workflows/pr-title.yml@master
```

To block merging, make **call-pr-title / Validate PR title** a required check in
the base branch's protection rules.

## Options

All inputs are optional; without them the check behaves as above.

| Input | Default | Description |
|---|---|---|
| `types` | Conventional Commit types | Allowed types, one regex per line |
| `scopes` | any | Allowed scopes, one regex per line (auto-wrapped in `^…$`) |
| `require-scope` | `false` | Require a scope |
| `subject-pattern` | any | Regex the subject must match |
| `subject-pattern-error` | action default | Error shown when `subject-pattern` fails (`{subject}`, `{title}` placeholders) |
| `validate-single-commit` | `false` | For one-commit PRs also validate the commit message, which GitHub suggests for the squash commit instead of the title |
| `single-commit-matches-title` | `false` | With `validate-single-commit`, also require the commit message to equal the title |
| `wip` | `false` | `[WIP] …` titles keep the check pending. Needs `statuses: write` |
| `ignore-labels` | none | Labels that skip validation, one per line. Add `labeled`, `unlabeled` to the caller's `types` |
| `comment` | `false` | Post the error as a sticky PR comment and delete it once fixed. Needs `pull-requests: write` |

The reusable workflow declares no permissions, so the caller's grant applies: give the
extra permissions only when you turn on `wip` or `comment`.

Strict variant, as used by standalone modules:

```yaml
on:
  pull_request:
    types: [opened, edited, synchronize, reopened, labeled, unlabeled]

permissions:
  pull-requests: write

jobs:
  call-pr-title:
    uses: studioraz/ci-templates/.github/workflows/pr-title.yml@master
    with:
      # Optional Jira key, then a lowercase description: "ALFP-107 add x" or "add x".
      subject-pattern: ^([A-Z][A-Z0-9]+-\d+ )?(?![A-Z]).+$
      subject-pattern-error: |
        The subject "{subject}" must start lowercase, optionally after a Jira key
        ("ALFP-107 add express checkout").
      validate-single-commit: true
      single-commit-matches-title: true
      ignore-labels: ignore-semantic-pull-request
      comment: true
```
