# Changelog

All notable changes to Custom Branding are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/).
Versions follow **CalVer `YYYY.M.R`** (year, month with no leading zero, revision within the month),
**not** Semantic Versioning: `2026.8.1` says when it was released, nothing about compatibility.

## [Unreleased]

## [2026.8.2] - 2026-08-30

### 🔧 Changed

- **`manifest.json`:** keys reordered to `domain`, `name`, then alphabetical, which is what
  `hassfest` requires. The CI failed without it.

### 🐛 Fixed

- **`NameError: name 'DATA_UNDO_JS' is not defined` when setting up the integration.** The constant
  lived in `const.py` but was missing from the import list in `__init__.py`, so `async_setup_entry`
  died on the line right after registering the JS module.

  The failure was **partial and misleading**: the static routes, the PWA manifest and the JS module
  had all been applied before the line that raised, so the icons did change and `/manifest.json`
  already carried the brand name, while the entry showed up as failed under Devices and Services
  and the login page title rewrite never ran at all.

## [2026.8.1] - 2026-08-30

### ✨ Added

- First release. Brands a Home Assistant install from the UI: browser tab, login screen, onboarding,
  loading logo, Open Home Foundation footer, Windows tiles, Safari pinned tab, and the name and icons
  of the installed app (PWA).
- **One static route per file** over `/static/icons/*` and `/static/images/*`. aiohttp resolves by
  longest matching prefix, so these win over the frontend's own `/static` directory resource without
  depending on registration order. This is what reaches the **login screen**, which no JS module can:
  `extra_module_url` is never injected into `authorize.html`.
- **Config flow and options flow**, single instance, with validation of the asset folder before the
  entry is created. English and Brazilian Portuguese translations.
- **ES module loaded by the integration itself** (`frontend.add_extra_js_url`) for the tab title and
  the `apple-mobile-web-app-title` / `application-name` metas, so nothing has to be added to
  `configuration.yaml`. It re-applies on panel changes, because Home Assistant rewrites
  `document.title` on every navigation with the product name hardcoded.
- **PWA manifest rewrite** via `add_manifest_json_key`, rebuilding both icon purposes together so the
  Android adaptive icon is not lost, and zeroing `prefer_related_applications` so Chrome stops
  offering the Companion App instead of the PWA.
- **Optional login and onboarding title rewrite**, off by default. Keeps a backup, marks the file,
  regenerates the `.gz` and `.br` sidecars (aiohttp serves those with priority, so patching only the
  plain file would be invisible to every real browser), and reapplies on every start so an image
  update does not undo it.
- Actions `custom_branding.apply` and `custom_branding.restore`.
- CI with `hassfest` and `hacs/action`.

[Unreleased]: https://github.com/self-labs/ha-custom-branding/compare/v2026.8.2...HEAD
[2026.8.2]: https://github.com/self-labs/ha-custom-branding/compare/v2026.8.1...v2026.8.2
[2026.8.1]: https://github.com/self-labs/ha-custom-branding/releases/tag/v2026.8.1
