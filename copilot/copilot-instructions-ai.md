# Copilot Project Instructions

## 1. Overview
This file enables AI coding assistants to generate features aligned with the project’s architecture and style. It is based only on actual, observed patterns from the codebase—never invented practices.

## 2. File Category Reference

### magento-modules
- **What:** Magento 2 modules for business logic, features, and integrations.
- **Examples:** app/code/SR/*, app/code/Magento/*
- **Key Conventions:**
  - PascalCase class names, namespaced by vendor/module
  - Service contracts (interfaces) for repositories/services
  - Constructor DI only; no ObjectManager
  - Plugins/events for extension
  - No helpers for business logic
  - Strict typing

### theme-files
- **What:** Hyvä theme customizations (frontend, layout, templates)
- **Examples:** app/design/frontend/*, app/design/adminhtml/*
- **Key Conventions:**
  - AlpineJS for JS, Tailwind for CSS
  - Minimal, scoped layout XML
  - No new frontend tooling
  - No inline JS/CSS

### cli-scripts
- **What:** CLI scripts for admin/dev tasks
- **Examples:** ddev magento, ddev n98
- **Key Conventions:**
  - Use ddev n98 for all CLI
  - No hardcoded secrets
  - Clear, functional naming

### configuration
- **What:** Environment and system config
- **Examples:** app/etc/*, config/*, setup/config/*
- **Key Conventions:**
  - Env vars for secrets
  - No secrets in repo
  - Uppercase, underscore-separated names

### test-suites
- **What:** Automated tests
- **Examples:** dev/tests/*
- **Key Conventions:**
  - PHPUnit for all tests
  - Test classes end with Test
  - No network calls
  - Use Magento integration test framework

### static-assets
- **What:** Frontend assets (JS, CSS, images)
- **Examples:** pub/static/*, pub/media/*, app/design/frontend/*/web/*
- **Key Conventions:**
  - Hyvä conventions (AlpineJS, Tailwind)
  - No inline JS/CSS
  - Feature-specific naming

### build-tools
- **What:** Build/dependency management
- **Examples:** Gruntfile.js.sample, package.json, composer.json
- **Key Conventions:**
  - Composer for PHP, npm for frontend
  - No unapproved dependencies

### deployment
- **What:** Deployment automation
- **Examples:** deployer.php, deployer/*
- **Key Conventions:**
  - Use deployer.php
  - No manual steps
  - No secrets in scripts

### patches
- **What:** Code patches
- **Examples:** patches/*
- **Key Conventions:**
  - All patches in patches/
  - No vendor hacks
  - Descriptive names, documented purpose

### docs
- **What:** Documentation
- **Examples:** CHANGELOG.md, SECURITY.md, README.md
- **Key Conventions:**
  - Keep docs up to date
  - Maintain changelog and security docs

## 3. Feature Scaffold Guide
- **Determine file categories:** Use the above reference to decide which categories are needed for a new feature.
- **File placement:**
  - Magento modules: app/code/SR/YourModule/
  - Theme: app/design/frontend/SR/yourtheme/
  - CLI: bin/
  - Config: app/etc/, config/
  - Tests: dev/tests/
  - Assets: app/design/frontend/SR/yourtheme/web/
- **Naming/structure:**
  - Use PascalCase for PHP classes, kebab-case for assets
  - Place logic in service classes, not helpers
  - Use plugins/events for extension
  - Keep layout XML minimal
- **Example:**
  - New product import feature:
    - app/code/SR/ProductImport/Model/Importer.php
    - app/code/SR/ProductImport/etc/db_schema.xml
    - app/code/SR/ProductImport/Plugin/SomePlugin.php
    - dev/tests/unit/SR/ProductImport/Model/ImporterTest.php
    - app/design/frontend/SR/yourtheme/web/js/product-import.js

## 4. Integration Rules
- All data access/business logic uses repositories and service contracts
- All dependencies injected via constructors (no ObjectManager)
- Plugins/events for extension, not preferences unless required
- No helpers for business logic
- All frontend customizations use Hyvä conventions (AlpineJS, Tailwind)
- No new frontend tooling unless requested
- No hardcoded secrets or credentials
- All patches in patches/, never patch vendor code directly
- All tests must be deterministic, no network calls

## 5. Example Prompt Usage
> "Create a CLI script to reindex all Magento data and log the output."

Copilot should generate:
- bin/reindex-all
- Uses ddev n98 indexer:reindex:all
- Logs output to var/log/reindex.log
- No hardcoded credentials
- Script is documented and named for its function

> "Add a new Hyvä-styled banner block to the homepage."

Copilot should generate:
- app/design/frontend/SR/yourtheme/Magento_Theme/layout/cms_index_index.xml
- app/design/frontend/SR/yourtheme/templates/html/banner.phtml
- Uses AlpineJS for interactivity, Tailwind for styling
- No inline JS/CSS

---

This file must be kept up to date with project conventions. Do not invent best practices or add categories not present in the codebase.
