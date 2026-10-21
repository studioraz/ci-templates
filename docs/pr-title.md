# pr-title.yml

Fails a PR whose title is not a [Conventional Commit](https://www.conventionalcommits.org/),
using [`amannn/action-semantic-pull-request`](https://github.com/amannn/action-semantic-pull-request).
With squash merging the PR title becomes the commit subject that
[`release-calver.yml`](release-calver.md) turns into a changelog entry.

Allowed types: `feat`, `fix`, `perf`, `revert`, `docs`, `style`, `refactor`,
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
