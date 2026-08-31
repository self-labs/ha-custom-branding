# Changelog

All notable changes to Custom Branding are documented in this file.

The format is based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/).
Versions follow **CalVer `YYYY.M.R`** (year, month with no leading zero, revision within the month),
**not** Semantic Versioning: `2026.8.1` says when it was released, nothing about compatibility.

## [Unreleased]

## [2026.8.6] - 2026-08-31

### ✨ Added

- **One-click install button** in the README, through
  [my.home-assistant.io](https://my.home-assistant.io/). It uses the
  `hacs_repository` redirect, which is the one that opens a custom repository
  inside HACS; the `supervisor_add_addon_repository` redirect that shows up in
  some READMEs is for Supervisor add-ons and does nothing on a plain Docker
  install. The manual steps moved into a collapsed block.
- **Section explaining where the integration icon does and does not show up.**
  The `brand/` folder covers Settings > Devices & services, served through
  `/api/brands/`. It does **not** cover the HACS panel, which resolves icons
  from its own CDN, fed by the `home-assistant/brands` repository, and ignores
  the local folder entirely. Clearing the browser cache changes nothing there,
  because nothing is cached: the image genuinely does not exist at the address
  HACS asks for.

### 🐛 Fixed

- **The 2026.8.5 entry claimed the integration "no longer depends on being
  listed in the `home-assistant/brands` repository".** True for Devices &
  Services, false for the HACS panel, and the sentence sent at least one person
  looking for the icon in the wrong screen. Corrected in place.

## [2026.8.5] - 2026-08-30

### ✨ Added

- **Trademark and responsible use section**, built on the primary sources rather
  than on impressions: the Open Home Foundation's own wording in
  `home-assistant/assets` ("not available for commercial use without express
  written permission"), the `HOME ASSISTANT` registration, and section 6 of the
  Apache 2.0 licence, which excludes trademark rights from what the licence
  grants.

  The point it makes: this integration does not use their marks, it removes
  them, and the software underneath is still Home Assistant. Rebranding an
  install you operate is a local change; delivering it as your own product with
  the origin removed is a different thing. The same warning now appears **in the
  setup form**, which is where the decision actually gets made, in all three
  languages.

- **`brand/` folder with the integration icon.** Devices and Services was showing
  "icon not available" in place of it. Home Assistant 2026.3 and newer serve
  these local files through `/api/brands/`, which is what fixes that screen.

  **It does not fix the HACS panel.** HACS resolves icons from its own CDN, fed
  by the `home-assistant/brands` repository, and ignores the local `brand/`
  folder entirely. Until a PR adds `custom_integrations/custom_branding/` there,
  HACS keeps showing "icon not available", and no amount of cache clearing
  changes that.

  A painter's palette, matching the emoji the README already used. Not the Home
  Assistant house, on purpose: that one is theirs.

### 🔧 Changed

- **CI now runs the `brands` check.** It was suppressed with `ignore: brands`
  while there was no icon to check.

## [2026.8.4] - 2026-08-30

### ✨ Added

- **`login-icon.svg`, an optional asset that takes over the login screen slot.**
  That slot is a PNG in the frontend markup and a PNG cannot carry a media
  query, so a fixed-colour icon is wrong in one of the two themes and an opaque
  background becomes a bright square floating in the dark theme. aiohttp picks
  the `Content-Type` from the file on disk rather than from the URL, so an SVG
  served at the `.png` route reaches the browser as `image/svg+xml` and renders
  as SVG, media query and all. The PWA manifest keeps pointing at the real PNG,
  since an app icon has to be a bitmap.
- **README section on following the light and dark theme**, with the measured
  reason it matters: the login and loading screens are drawn on `#fafafa` or
  `#111111` depending on the theme, and no single colour clears 3:1 against
  both. Also documents that the `CDATA` around the CSS is mandatory, because an
  SVG served as `image/svg+xml` is parsed as strict XML.

## [2026.8.3] - 2026-08-30

An adversarial review of the Python (four independent lenses, every finding
re-checked against the core source before being accepted) turned up seven real
defects. Six of the seven are silent: the entry reports success while the
integration serves the wrong thing or leaves state behind.

### ✨ Added

- **`translations/pt.json`.** Home Assistant does not fall back between language
  variants, so an install set to `pt` was getting English instead of the `pt-BR`
  strings. Same wording for now; split the files if the two ever diverge.

### 🔧 Changed

- **Minimum Home Assistant is now 2024.12, was 2024.7.** Two independent floors
  apply and the higher one wins: `async_register_static_paths` (2024.7) and the
  framework-provided `OptionsFlow.config_entry` property (2024.12). On 2024.11
  and older the base class has no `config_entry` at all, so opening **Configure**
  raised `AttributeError` on exactly the versions HACS was letting install.
- **README badge:** the HACS one used a logo slug that did not render in the HACS
  panel. It now uses the same slug as the badge next to it.

### 🐛 Fixed

- **Changing the asset folder kept serving the old one, silently.** The route
  guard was a set of URLs, so a second setup found every URL already present,
  registered nothing, and logged nothing, while the core had frozen the old path
  into a `functools.partial` at registration time. Deleting the old folder then
  404'd all 19 icons **without falling back** to the Home Assistant originals,
  because the per-file route still wins by longest prefix. The guard now maps
  URL to path and raises `ConfigEntryError` asking for a restart, which is the
  only thing that can actually rebind a route.
- **`restore` running against `apply` could destroy a backup.** Both land on the
  executor thread pool and the restore action does not go through the config
  entry lock, so one thread could delete the backup another had just recreated,
  leaving a marked file that `_patch_one` refuses to touch and `restore_titles`
  skips forever: the original page unrecoverable without a `docker pull`. Both
  functions now hold a module lock, and the temp file carries the thread id.
- **The tab froze when the brand name contained "Home Assistant".** `applyTitle`
  replaced the product name on every pass, so a brand like "My Home Assistant"
  grew the title on each run and the `MutationObserver` re-fired. The callbacks
  are microtasks, so the loop never yielded to the event loop. It now remembers
  the title it wrote, read back from the DOM.
- **The HTML patch was only undone when the in-memory list was populated.** The
  patch is on-disk state that outlives the process, and that list is empty on
  any boot where setup raised before layer 3. The unload now always tries the
  restore, and `async_remove_entry` was added so deleting an entry that never
  reached LOADED still reverts the files inside the container.
- **The PWA manifest was never reverted.** Unloading the integration left the
  brand name and icons in `/manifest.json`, and `if icons:` let the icons of a
  previous asset folder survive a reload. The core values are now snapshotted
  before the first overwrite and restored on unload.
- **`HomeAssistantError` reached the UI as a bare traceback.** Setup failures now
  raise `ConfigEntryError`, so the reason shows up in Devices and Services
  instead of only in the log. `OSError` from scanning the folder is handled too.

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

[Unreleased]: https://github.com/self-labs/ha-custom-branding/compare/v2026.8.6...HEAD
[2026.8.6]: https://github.com/self-labs/ha-custom-branding/compare/v2026.8.5...v2026.8.6
[2026.8.5]: https://github.com/self-labs/ha-custom-branding/compare/v2026.8.4...v2026.8.5
[2026.8.4]: https://github.com/self-labs/ha-custom-branding/compare/v2026.8.3...v2026.8.4
[2026.8.3]: https://github.com/self-labs/ha-custom-branding/compare/v2026.8.2...v2026.8.3
[2026.8.2]: https://github.com/self-labs/ha-custom-branding/compare/v2026.8.1...v2026.8.2
[2026.8.1]: https://github.com/self-labs/ha-custom-branding/releases/tag/v2026.8.1
