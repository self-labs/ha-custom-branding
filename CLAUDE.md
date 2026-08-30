# Custom Branding: Repository Conventions (for AI agents)

A Home Assistant **custom integration**, distributed through HACS, that replaces the Home Assistant
artwork and product name on an installation with the operator's own.

This is real Python that runs inside someone's home server. Unlike a documentation repo, a mistake
here breaks a live instance, so correctness and reversibility come before feature count.

## Language

- **Code, comments, docstrings, README, CHANGELOG, commit messages: English.**
- **User-facing strings** live only in `translations/*.json`. `en.json` is the source of truth and the
  fallback; `pt-BR.json` mirrors it. Note the file name: `pt-BR.json`, hyphen and uppercase BR.
- Brazilian Portuguese in translation files uses **full, correct accentuation**.
- **Never use em dashes or en dashes** anywhere: code comments, README, commit messages, translation
  strings. Use a comma, colon, parentheses, or a new sentence.

## Layout (HACS requires this exact shape)

```text
custom_components/custom_branding/    # exactly ONE folder under custom_components/
├── __init__.py                       # setup, routes, manifest, actions
├── config_flow.py                    # UI configuration
├── const.py                          # every constant, including the asset -> URL map
├── html_patch.py                     # the only module that writes inside the container
├── manifest.json                     # domain MUST equal the folder name
├── services.yaml
├── icons.json
├── frontend/branding.js              # ES module served to the browser
└── translations/{en,pt-BR}.json
hacs.json                             # at the repo ROOT
README.md, LICENSE, CHANGELOG.md      # all three required by HACS
```

`hacs.json` uses `extra=PREVENT_EXTRA`: **an unknown key fails validation**. Only `name`,
`content_in_root`, `zip_release`, `filename`, `hide_default_branch`, `country`, `homeassistant`,
`hacs` and `persistent_directory` are accepted.

## What HACS and hassfest each require

They validate different things, so the union is what matters. Required in `manifest.json`:
`domain`, `name`, `version`, `documentation`, `issue_tracker`, `codeowners`, `iot_class`.

- `version` missing means the integration is **blocked from loading** by Home Assistant itself, on top
  of failing both CI checks.
- `domain` must equal the directory name.
- `documentation` must not point at `home-assistant.io`.
- `codeowners` must be a **list**, never a bare string.
- The GitHub repo needs a description, at least one non-generic topic, issues enabled, and an
  **OSI-approved licence** (a newer HACS check, still absent from the published docs).
- `ignore: brands` in the workflow is an **active key**, not a comment. Remove it only after adding
  `custom_components/custom_branding/brand/icon.png`.

## Design rules (the reasoning behind the code)

1. **Public API first.** `async_register_static_paths`, `add_manifest_json_key`, `add_extra_js_url`
   and `remove_extra_js_url` are the entire supported surface. Anything beyond it is a last resort
   and belongs in `html_patch.py`, behind an option that defaults to off.
2. **Register routes per FILE, never per directory.** aiohttp resolves by longest matching prefix, so
   `/static/icons/favicon.ico` beats the frontend's `/static` resource whatever the order. Registering
   the directory `/static/icons` shadows the whole subtree and 404s every file not shipped.
3. **Never hardcode the frontend package path.** It carries the Python version of the base image
   (already moved from 3.13 to 3.14). Always resolve it with `hass_frontend.where()`.
4. **Rewriting a text file means rewriting its sidecars.** Every HTML, SVG and XML in the frontend
   ships with `.gz` and `.br` twins, and aiohttp serves those first. Patching only the plain file is
   invisible to every real browser.
5. **Reversible by construction.** Anything written inside the container takes a backup first,
   carries a marker, and reapplies from the pristine copy rather than stacking edits.
6. **Blocking I/O goes through `hass.async_add_executor_job`.** Scanning a folder, reading a file,
   and importing `hass_frontend` all touch the disk.
7. **Missing asset is not an error.** Whatever the user did not provide keeps the Home Assistant
   original, and the integration logs at debug or warning, never raising.

## Config flow

- `single_config_entry: true` in the manifest is the strongest guard against a second instance.
- `OptionsFlow` takes **no constructor argument** and never assigns `self.config_entry`: the setter
  was deprecated in 2024.12 and removed in 2025.12. The base class exposes it as a read-only property.
- Actions are registered in `async_setup`, not `async_setup_entry`, so `restore` still exists when the
  entry fails to load.
- `integration_type: service`. `helper` implies an entity and `system` hides the integration from the
  add list.

## Versioning and releases

CalVer `YYYY.M.R` in `manifest.json`, matching the git tag (`v2026.8.1`). HACS shows releases when
they exist and offers the update through an `update.*` entity. Bump the version **and** close the
`[Unreleased]` section of `CHANGELOG.md` in the same change.

## Commits

- **Conventional Commits, in English.** Scope is the module: `feat(config_flow): validate asset dir`,
  `fix(html_patch): regenerate brotli sidecar`.
- **Never commit or push without the maintainer explicitly asking.** Leave the work in the tree and
  report that it is ready.
