# db-sync.yml

Copies one environment's database into another, typically production → staging, with
[`studioraz/deployer-magento`](https://github.com/studioraz/deployer-magento):

1. **dump** job (GitHub environment = source): `dep db:pull <source> -o import=false` dumps the
   source database with n98-magerun2 and uploads it as the `db-sync-dump` artifact (kept 1 day).
2. **import** job (GitHub environment = target): `dep db:push <target>` optionally backs up the
   target database, imports the dump in maintenance mode, re-applies `config/store/<target>` with
   `config:data:import`, clears `cron_schedule`, then runs `setup:upgrade --keep-generated` and
   `cache:flush`.

The target can never be `production`. The data isn't anonymized: the artifact and the target
hold real customer data, so restrict who can run Actions and access the target.

## Usage

Copy [`callers/db-sync.yml`](../callers/db-sync.yml) and set the project's heavy optional tables
as the `exclude-tables` default.

## Inputs

| Input | Default | Description |
|---|---|---|
| `source-environment` | `production` | Deployer host and GitHub environment to dump |
| `target-environment` | `staging` | Deployer host and GitHub environment to overwrite |
| `confirm` | required | Must equal `target-environment` |
| `dump-mode` | `stripped` | `stripped` dumps `@trade` (customers, orders, quotes) without data; `full` keeps all data |
| `exclude-tables` | `""` | Space-separated tables (wildcards allowed, e.g. `mst_seo_audit_*`) or n98 groups (`@log @sessions`) dumped without data, in both modes |
| `backup` | `true` | Dump the target database to `<deploy_path>/backups/` first (last 3 kept) |
| `php-version` | `8.3` | PHP version for Deployer |

## Requirements

- `SSH_CONNECTION_PRIVATE_KEY` secret in both GitHub environments (same as `build-and-deploy.yml`).
- `deploy.php` defines hosts named like the environments, and `config/store/<target>/` overrides
  everything that must differ from the source: base URLs, integration credentials and sandbox
  modes, email sending.
- A `studioraz/deployer-magento` release with the `db:push` task.
- Recommended: required reviewers on the target environment.

## Restore a backup

```bash
dep run '{{bin/n98}} db:import --compression=gzip --drop-tables {{deploy_path}}/backups/<file>.sql.gz' staging
```
