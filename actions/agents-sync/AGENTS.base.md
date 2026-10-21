# Studioraz organization instructions

Applies to every Studioraz Magento 2 project. Project-specific rules follow in the *Project specifics* section.

## 0. Non‑Negotiables

* **PHP compatibility:** PHP **8.2+** only.
* **Magento CLI:** always use `ddev n98`, never `bin/magento` unless explicitly requested.
* **Prefer OOTB:** use Magento/Hyvä built‑ins over custom implementations.
* **Minimal diffs:** don’t rewrite whole files; patch the smallest surface area.
* **No secrets:** never hardcode credentials, API keys, or tokens.

---

## 1. Determine Versions & Stack (Before Coding)

* Determine **current Magento version** and **supported PHP version** from Adobe Commerce/Magento system requirements.
* If a feature depends on version (PHP attributes/enums, new Magento APIs), choose the **most conservative compatible** approach.

### Tech Stack

* Magento 2 (Open Source / Adobe Commerce)
* PHP 8.x
* Hyvä theme
* JavaScript (Grunt / Node)
* Composer + npm
* nginx
* PHPUnit + Magento integration tests
* DDEV local dev

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

### Hyvä / Frontend

* Respect Hyvä patterns:

  * AlpineJS for interactivity
  * Tailwind for styling
* Do not introduce new tooling unless asked.
* Keep layout XML minimal and scoped.

### Naming & Structure

* New modules live in: `<root_magento>/app/code/SR/<ModuleName>`.
* Naming: `SR_VendorFeature` (PascalCase module name).
* Class paths follow Magento conventions:

  * `Controller`, `Model`, `Plugin`, `Observer`, `ViewModel`, `Ui/Component`, etc.

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

* Assume local dev is via DDEV.
* Commands must be provided as `ddev n98 <command>`.
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
* **Releases are automated** (CalVer `YYYY.MM.DD.N`): never edit `CHANGELOG.md` or `VERSION` by hand, and never merge or edit the `chore(release): release …` PR's branch manually.

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
* **Build:** `ddev npm run build-all`
* **Docs:** `CHANGELOG.md`, `SECURITY.md`, `README.md`
* **Tests:** `dev/tests/`, `dev/tools/`
* **Assets:** `pub/static/`, `pub/media/`, `pub/errors/`
* **Vendor:** `vendor/`, `package-lock.json`
* **Deploy:** `deployer.php`,`deployer/*`
* **DDEV:** `.ddev/*`
