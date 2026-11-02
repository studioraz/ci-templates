# Studio Raz Organization Instructions

Applies to every Studio Raz Magento 2 / Mage-OS project. Project-specific rules follow in the *Project specifics* section.

## 0. Non‑Negotiables

* **PHP compatibility:** target the PHP version the project's `composer.json` allows — `config.platform.php` if set, otherwise the lowest version in `require.php` (e.g. `~8.2.0||~8.3.0` → write PHP 8.2-compatible code).
* **Magento CLI:** with DDEV always use `ddev n98`, never `bin/magento` unless explicitly requested. Without DDEV (cloud agents, CI) don't run Magento CLI at all — see *Development Environment Rules*.
* **Prefer OOTB:** use Magento built‑ins (and Hyvä built‑ins on Hyvä projects) over custom implementations.
* **Minimal diffs:** don’t rewrite whole files; patch the smallest surface area.
* **No secrets:** never hardcode credentials, API keys, or tokens.

---

## 1. Determine Versions & Stack (Before Coding)

* Determine the **distribution and version** from `composer.json` / `composer.lock`:
  * `magento/product-community-edition` → **Magento Open Source**; `magento/product-enterprise-edition` → **Adobe Commerce**.
  * `mage-os/product-community-edition` → **Mage-OS**. Mage-OS versions are numbered separately from Magento; check the Mage-OS release notes for the Magento version it is based on.
* Determine the **supported PHP version** as described in *Non-Negotiables* (from `composer.json`).
* If a feature depends on version (PHP attributes/enums, new framework APIs), choose the **most conservative compatible** approach.
* **Mage-OS projects:** PHP namespaces, module names and APIs are the same as Magento (`Magento\…`, `Magento_Catalog`), so write code the same way. Composer packages are published under `mage-os/*` — require `mage-os/…` core packages instead of `magento/…` ones (third-party extensions are unaffected).

### Tech Stack

* **Magento 2** (Open Source / Adobe Commerce) or **Mage-OS** — differs per project, see above
* PHP 8.x
* Frontend theme: **Hyvä** or **Luma** — differs per project, see *Frontend* below
* JavaScript (Grunt / Node)
* Composer + npm
* nginx
* PHPUnit + Magento integration tests
* DDEV local dev (not available in cloud agents such as the Copilot coding agent, or in CI)

---

## 2. Architectural Defaults

* **Service contracts first:** prefer repositories + `SearchCriteriaInterface` to collections.
* **DI everywhere:** constructors only; no `ObjectManager` usage.
* **Plugins over preferences** when extending framework classes.
* **Events/observers** for cross‑module extension points.
* **Declarative schema** (`db_schema.xml`) over setup scripts.
* **Avoid deprecated APIs** (`@deprecated`).
* **Avoid helpers** for business logic; use service classes.

---

## 3. Coding Style & Conventions

### PHP / Magento

* Follow Magento Coding Standards + PSR‑12.
* Prefer strict typing when safe (`declare(strict_types=1);`).
* Add parameter/return types where Magento interfaces allow.
* Keep methods small and single‑purpose.
* Favor immutability and pure functions for business logic.
* Use translation via `__()` only in presentation or message contexts.

### Frontend (Hyvä or Luma)

Projects use either **Hyvä** or **Luma**. Determine which before writing frontend code:

1. The *Project specifics* section of this file, if it states the theme.
2. Otherwise: `hyva-themes/*` packages in `composer.json`, or a theme in `app/design/frontend/` whose `theme.xml` has parent `Hyva/default` (or another Hyvä theme) → **Hyvä**. Parent `Magento/luma` or `Magento/blank` and no Hyvä packages → **Luma**.

Never mix the two stacks.

**Hyvä projects**

* AlpineJS for interactivity, Tailwind for styling.
* No RequireJS, Knockout, jQuery or LESS in storefront code; use Hyvä compatibility modules for third‑party extensions.

**Luma projects**

* RequireJS modules; jQuery widgets or UI components (Knockout) for interactivity.
* LESS for styling, following Magento's theme structure (`_extend.less`, `_module.less`); no Tailwind or AlpineJS.
* Extend core JS with RequireJS mixins rather than overriding files.

**Both**

* Do not introduce new tooling unless asked.
* Keep layout XML minimal and scoped.

### Building the Frontend

Commands below are in DDEV form. Without DDEV, run npm/grunt directly (drop the `ddev` / `ddev exec` prefix) and skip steps that need the Magento CLI — see *Development Environment Rules*.

Find the build command in this order:

1. The build command in *Project specifics*, if given.
2. `ddev npm run build-all` if the root `package.json` defines a `build-all` script.
3. Otherwise the theme-specific steps below.

**Hyvä** — rebuild after changing `.phtml`, layout XML, Tailwind config or theme CSS (Tailwind only generates classes it finds):

* Run the build script from the theme's `web/tailwind/package.json`, e.g. `ddev exec npm --prefix app/design/frontend/<Vendor>/<theme>/web/tailwind run build`.
* Whether the generated `web/css/styles.css` is committed follows the project (check `.gitignore` and history); don't change that convention.

**Luma** — after changing LESS, RequireJS config or JS:

* `ddev exec grunt refresh` if the project has a `Gruntfile.js`; otherwise remove `pub/static/frontend/<Vendor>/<theme>` and `var/view_preprocessed`, then `ddev n98 cache:clean`.
* Don't run `setup:static-content:deploy` unless the project runs in production mode.

**Both**

* Never commit `pub/static/`, `var/` or `generated/`.
* Run the build before finishing a frontend change and fix any errors it reports.
* If you can't build (no DDEV or Node available, e.g. in a cloud agent), say so in the PR description instead of skipping silently.

### Naming & Structure

* New modules live in: `<root_magento>/app/code/SR/<ModuleName>`.
* Naming: `SR_VendorFeature` (PascalCase module name).
* Class paths follow Magento conventions:

  * `Controller`, `Model`, `Plugin`, `Observer`, `ViewModel`, `Ui/Component`, etc.

### Identifier Naming Conventions

`<Module>` = module name without `SR_` (e.g. `DeliveryMatrix`); `<module>` = its lowercase key with no separators (e.g. `deliverymatrix`, `herp`, `ordersync`); `<module_snake>` = snake_case form (e.g. `delivery_matrix`, `credit_accumulation`). A shorter, unambiguous key is fine (e.g. `credit` for `CreditAccumulation`) — pick one per module and use it everywhere.

| Identifier | Convention | Example |
|---|---|---|
| Composer package | `sr/module-<module-kebab>` | `sr/module-herp-account-invitation` |
| DB table (new) | `studioraz_<module>_<entity>` | `studioraz_credit_ledger`, `studioraz_delivery_rule` |
| Column added to a core table | `sr_<module>_<field>` (avoid clashes with core/3rd‑party) | `sales_order.sr_credit_amount` |
| `referenceId` (index/constraint) | UPPERCASE table + columns, `_UNQ` for unique | `STUDIORAZ_CREDIT_RULE_CUSTOMER_UNQ` |
| CLI command | `sr:<module>:<command-name>` (kebab-case action, extra `:` segments allowed) | `sr:credit:month-end`, `sr:ordersync:seed` |
| CLI command class | `Console/Command/<Action>Command.php`, name in a `private const NAME` | `MonthEndCommand` |
| Admin config section | `sr<module>`; paths `sr<module>/<group>/<field>` | `srdeliverymatrix/create_shipment_policy/enable` |
| Config path constants | `XML_PATH_<FIELD>` constants + typed getters in `Model/Config.php` (no helpers) | `XML_PATH_ENABLED` |
| ACL resource | `SR_<Module>::<resource>`; root `SR_<Module>::main`, config `SR_<Module>::configuration`, under `SR_Base::srbase` | `SR_HERP::invitations` |
| Admin/frontend route | `id` and `frontName` `sr<module>` | `srdeliverymatrix` |
| UI component files | `sr<module>_<entity>_listing.xml` / `_form.xml` | `srherp_invitation_listing.xml` |
| Layout handles | `<route>_<controller>_<action>` | `srdeliverymatrix_deliveryetarule_edit` |
| Plugin / observer `name` | `sr_<module_snake>_<purpose>` | `sr_credit_accumulation_place_order` |
| Custom events dispatched | `sr_<module>_<subject>_<when>` | `sr_ordersync_before_save_order` |
| Cron job | `sr_<module_snake>_<job>` | `sr_credit_accumulation_month_end` |
| Message queue topic / consumer | `sr<module>.<entity>.<action>`; consumer `…consumer` | `srherp.heshin.sync.async` |
| Virtual types | `Sr<Module><Purpose>` (PascalCase) | `SrHerpMainLogger` |
| Log file | `var/log/sr<module>.log` via a virtual logger + handler | `var/log/srherp.log` |
| Customer-data section | `sr-<module-kebab>` | `sr-credit-accumulation` |
| Translations | `i18n/<locale>.csv` (`en_US.csv`, plus store locales e.g. `he_IL.csv`) | — |

* Apply these to **new** identifiers. Don't rename existing tables, columns, config paths, ACL ids or cron/queue names that deviate (e.g. `sr_herp_agent`, `srherp_invoice_sync`) — renaming breaks stored data, config and permissions unless a migration is part of the task.


---

## 4. Output Format for Copilot

* Provide **only the essential snippet** needed for copy/paste.
* Include file path headers when creating new files.
* If multiple files are required, list them in the order they should be created.
* Avoid long explanations unless explicitly asked.

Example:

```text
File: app/code/SR/Foo/Plugin/BarPlugin.php
<snippet>
```

---

## 5. Preferred Implementations (OOTB First)

Always check for an existing Magento solution before writing custom logic.

Use Magento interfaces/services such as:

* `\Magento\Framework\Serialize\SerializerInterface`
* `\Psr\Log\LoggerInterface`
* `\Magento\Framework\Escaper`
* `\Magento\Store\Model\StoreManagerInterface`
* `\Magento\Customer\Api\CustomerRepositoryInterface`

If a Magento feature exists:

1. Use it.
2. Only extend if it can’t meet requirements.
3. Keep extensions upgrade‑safe.

---

## 6. Testing Expectations

* If code changes business logic, **add tests**.
* **Unit tests** for pure logic.
* **Integration tests** for Magento wiring / DI / DB interactions.
* Tests must be deterministic and avoid network calls.

When suggesting tests:

* show minimal test skeletons
* don’t mock Magento internals unnecessarily

---

## 7. Development Environment Rules

Check whether DDEV is available (`command -v ddev`) before running any project command, and follow the matching mode.

### With DDEV (local development)

* Run everything inside DDEV:
  * Magento CLI: `ddev n98 <command>`, never `bin/magento`.
  * Composer / npm / PHP tools: `ddev composer …`, `ddev exec npm …`, `ddev exec vendor/bin/…`.
* For cache/di/static tasks, prefer explicit scopes/areas.

Common commands:

```bash
# DI compile
ddev n98 setup:di:compile

# Upgrade
ddev n98 setup:upgrade

# Flush cache
ddev n98 cache:flush

# Config dump
ddev n98 app:config:dump scopes
```

### Without DDEV (Copilot coding agent, CI, other cloud agents)

There is no database, Redis or OpenSearch, so:

* **Don't run** commands that need them: Magento CLI (`setup:upgrade`, `setup:di:compile`, cache, indexers, config) and integration tests. Don't fall back to `bin/magento`.
* **Do run** what works without services, calling the tools directly (only if `vendor/` / `node_modules/` are installed):
  * `composer validate`
  * `php -l <changed files>`
  * `vendor/bin/phpcs`, `vendor/bin/phpstan` (if configured in the project)
  * `vendor/bin/phpunit` for unit tests
  * Hyvä Tailwind build: `npm --prefix app/design/frontend/<Vendor>/<theme>/web/tailwind run build`
* **List the checks you could not run** in the PR description (e.g. "`setup:upgrade` and integration tests not run — no DDEV"), so a developer runs them locally.

---

## 8. GitHub Best Practices for Generated Code

### PR‑Friendly Changes

* Keep diffs focused on **one concern**.
* Avoid formatting unrelated lines.
* Don’t refactor unless requested.

### Conventional Commits (Required)

Every **commit message** and every **PR title** follows [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): JIRA-KEY description

Optional body: what changed and why.

BREAKING CHANGE: what breaks and how to migrate (only for breaking changes).
```

* **Types:**
  * `feat` new feature · `fix` bug fix · `perf` performance improvement · `revert` revert of an earlier change — these appear in the changelog.
  * `docs`, `style`, `refactor`, `test`, `build`, `ci`, `chore` — do not appear in the changelog.
* **Scope** (optional): the area changed, e.g. `checkout`, `catalog`, a module name.
* **Description:** lowercase, imperative, no trailing period ("add express checkout", not "Added express checkout.").
* **Jira key** right after the colon when there is a ticket: `fix(catalog): ALFP-112 hide badge on disabled products`.
* **Breaking changes:** `!` after the type/scope (`feat(api)!: …`) and a `BREAKING CHANGE:` footer.
* **Composer updates:** `chore(deps): update vendor/package`; use `fix(deps)` only when the update fixes a user-visible bug.
* Never write messages such as `wip`, `fix`, `changes`, `update files`, or `Merge …` for your own commits.

### PR Hygiene

* PRs are **squash merged**: the PR title (validated by CI) becomes the commit on the base branch, so it must describe the whole change. Split unrelated changes into separate PRs.
* Clear summary of what/why in the PR description.
* Include screenshots for UI changes.
* Include test evidence or rationale when skipping tests.
* **Releases are automated** (CalVer `YYYY.MM.DD.N`): never edit `VERSION` or the release changelog (`docs/CHANGELOG.md`, or `CHANGELOG.md` outside Magento projects) by hand, and never merge or edit the `chore(release): release …` PR's branch manually.
* **Standalone modules** release with SemVer through release-please: never edit `CHANGELOG.md`, `.release-please-manifest.json`, lines marked `x-release-please-version`, or the shared top-level keys of `release-please-config.json` by hand, and never edit the `chore(…): release …` PR's branch manually.

### Repository Safety

* No secrets in code or examples.
* Use env vars or Magento system config.
* Validate/escape all user input & output.
* Follow least‑privilege for ACL/resources.

---

## 9. Performance & Security Defaults

* Avoid loading full collections unnecessarily.
* Use pagination and filters.
* Cache where Magento provides caching layers.
* Sanitize inputs; escape outputs.
* Never trust request params.
* Prefer Magento’s validators and filters.

---

## 10. When Multiple Approaches Exist

Choose the most upgrade‑safe path:

1. OOTB feature
2. Plugin
3. Observer
4. Preference (only if required)

If trade‑offs matter, provide:

* the safest default
* a 1–2 line note about alternatives

---

## 11. Don’ts

* Don’t use `ObjectManager` directly.
* Don’t copy large chunks of vendor code unless required.
* Don’t introduce new dependencies without justification.
* Don’t change unrelated files.
* Don’t output secrets.

---

## 12. Repository Map (Quick Reference)

* **Source:** `app/code/`, `app/design/`, `app/etc/`, `lib/`
* **Config:** `composer.json`, `composer.lock`, `app/etc/`, `config/`, `nginx.conf.sample`, `Gruntfile.js*`, `package.json`, `patches/`
* **Build:** see *Building the Frontend* (`ddev npm run build-all` where defined)
* **Docs:** `CHANGELOG.md`, `SECURITY.md`, `README.md`
* **Tests:** `dev/tests/`, `dev/tools/`
* **Assets:** `pub/static/`, `pub/media/`, `pub/errors/`
* **Vendor:** `vendor/`, `package-lock.json`
* **Deploy:** `deployer.php`,`deployer/*`
* **DDEV:** `.ddev/*`
