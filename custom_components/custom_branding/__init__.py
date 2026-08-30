"""Custom Branding: put your own mark on a Home Assistant install.

Three layers, in order of how invasive they are:

1. One static route PER FILE over `/static/icons/*` and `/static/images/*`.
   aiohttp resolves by longest matching prefix, so a route for
   `/static/icons/favicon.ico` beats the frontend's `/static` directory
   resource regardless of registration order. This covers the browser tab, the
   login screen artwork, the loading logo and the footer, using only public
   API and without writing a single byte inside the container.

2. `frontend.add_manifest_json_key` for the installed app (PWA) name and icons,
   plus a small ES module for the tab title and the Apple/Windows app-name
   metas. Both are public helpers.

3. Optional, off by default: rewriting the `<title>` inside `authorize.html`
   and `onboarding.html`, which are the only two surfaces with no hook at all.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from pathlib import Path
from typing import Any
from urllib.parse import quote

import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import ConfigEntryError, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import html_patch
from .const import (
    ASSET_ROUTES,
    ASSETS_URL,
    CONF_ASSETS_DIR,
    CONF_BRAND_NAME,
    CONF_PATCH_HTML,
    DATA_MANIFEST_SNAPSHOT,
    DATA_PATCHED,
    DATA_ROUTES,
    DATA_UNDO_JS,
    DEFAULT_ASSETS_DIR,
    DEFAULT_BRAND_NAME,
    DOMAIN,
    JS_URL,
    MANIFEST_ANY_SIZES,
    MANIFEST_KEYS,
    MANIFEST_MASKABLE_SIZES,
    MODULE_URL,
    SERVICE_APPLY,
    SERVICE_RESTORE,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions once, at startup.

    Actions belong in async_setup, not in async_setup_entry: they must exist
    even when the entry failed to load, so the user can still call restore.
    """

    async def _handle_apply(call: ServiceCall) -> None:
        """Re-read the asset folder and apply everything again."""
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError("Custom Branding is not configured")
        await hass.config_entries.async_reload(entries[0].entry_id)

    async def _handle_restore(call: ServiceCall) -> None:
        """Undo the HTML patch, putting the original pages back."""
        restored = await _async_restore_html(hass)
        _LOGGER.info("Restored %d original page(s): %s", len(restored), restored)

    hass.services.async_register(DOMAIN, SERVICE_APPLY, _handle_apply, vol.Schema({}))
    hass.services.async_register(
        DOMAIN, SERVICE_RESTORE, _handle_restore, vol.Schema({})
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Custom Branding from a config entry."""
    options: dict[str, Any] = {**entry.data, **entry.options}
    brand_name: str = options.get(CONF_BRAND_NAME) or DEFAULT_BRAND_NAME
    assets_dir = Path(
        hass.config.path(options.get(CONF_ASSETS_DIR) or DEFAULT_ASSETS_DIR)
    )

    try:
        present = await hass.async_add_executor_job(_scan_assets, assets_dir)
    except OSError as err:
        raise ConfigEntryError(f"Could not read {assets_dir}: {err}") from err
    if present is None:
        raise ConfigEntryError(
            f"Asset folder not found: {assets_dir}. Create it, put your icons "
            f"there, then reload the integration."
        )

    known = set(ASSET_ROUTES)
    usable = present & known
    if unknown := present - known:
        _LOGGER.debug("Ignoring %d unrecognised file(s): %s", len(unknown), unknown)
    if not usable:
        _LOGGER.warning(
            "No recognised asset in %s. Expected names: %s",
            assets_dir,
            ", ".join(sorted(known)),
        )

    # --- Layer 1: one route per file -------------------------------------
    #
    # The core freezes the on-disk path into a functools.partial at registration
    # time, and aiohttp resolves same-path resources in registration order, so a
    # second route for an URL already taken can never be reached. Registration
    # is therefore once per Home Assistant start, and a folder change has to be
    # reported rather than swallowed: otherwise the entry reloads "successfully"
    # while every icon still resolves to the previous folder, and once that
    # folder is deleted they all 404 with no way back to the original artwork.
    domain_data: dict[str, Any] = hass.data.setdefault(DOMAIN, {})
    # url -> path actually registered during THIS Home Assistant boot.
    registered: dict[str, str] = domain_data.setdefault(DATA_ROUTES, {})

    wanted: dict[str, str] = {
        ASSETS_URL: str(assets_dir),
        MODULE_URL: str(Path(__file__).parent / "frontend"),
    }
    for filename in sorted(usable):
        wanted[ASSET_ROUTES[filename]] = str(assets_dir / filename)

    if stale := {
        url: registered[url]
        for url, path in wanted.items()
        if url in registered and registered[url] != path
    }:
        raise ConfigEntryError(
            "The asset folder changed, but aiohttp cannot replace a route while "
            f"Home Assistant is running. Restart Home Assistant to serve "
            f"{assets_dir}. Still stuck on: {stale}"
        )

    configs = [
        StaticPathConfig(url, path, url not in (ASSETS_URL, MODULE_URL))
        for url, path in wanted.items()
        if url not in registered
    ]
    if configs:
        await hass.http.async_register_static_paths(configs)
        # Only after the await: a failed registration must not leave the map
        # claiming the route exists.
        registered.update(wanted)
        _LOGGER.info("Serving %d branded asset(s) from %s", len(usable), assets_dir)

    # --- Layer 2: PWA manifest and the tab title -------------------------
    #
    # Snapshot once per Home Assistant start, before the first overwrite, so
    # unload can put the core values back. MANIFEST_JSON is a module singleton
    # and update_key replaces the whole key.
    if DATA_MANIFEST_SNAPSHOT not in domain_data:
        domain_data[DATA_MANIFEST_SNAPSHOT] = _snapshot_manifest()
    _apply_manifest(usable, brand_name)

    # The brand name travels in the query string so the module needs no build
    # step. Keep the exact URL around: remove_extra_js_url matches by string,
    # and the core stores these in a frozenset.
    js_url = f"{JS_URL}?brand={quote(brand_name, safe='')}"
    frontend.add_extra_js_url(hass, js_url)
    domain_data[DATA_UNDO_JS] = js_url

    # --- Layer 3: opt-in HTML patch --------------------------------------
    if options.get(CONF_PATCH_HTML):
        root = await hass.async_add_executor_job(_frontend_root)
        patched = await hass.async_add_executor_job(
            html_patch.patch_titles, root, brand_name
        )
        domain_data[DATA_PATCHED] = patched
        if patched:
            _LOGGER.info("Rewrote the title in: %s", ", ".join(patched))

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Undo what can be undone without a restart.

    The static routes stay: aiohttp has no public API to remove a route, and
    tearing one out through private attributes is not worth the risk. They only
    serve files, and a restart clears them.
    """
    domain_data: dict[str, Any] = hass.data.setdefault(DOMAIN, {})

    if js_url := domain_data.pop(DATA_UNDO_JS, None):
        frontend.remove_extra_js_url(hass, js_url)

    _restore_manifest(domain_data.pop(DATA_MANIFEST_SNAPSHOT, None))

    # No guard on DATA_PATCHED: the patch is on-disk state that outlives the
    # process, and that key is empty on any boot where setup raised before
    # layer 3, or where patch_titles returned [] after already writing a backup.
    # restore_titles is a no-op when there is no backup, so calling it is safe.
    if restored := await _async_restore_html(hass):
        _LOGGER.info("Restored %d original page(s): %s", len(restored), restored)
    domain_data.pop(DATA_PATCHED, None)

    _LOGGER.info(
        "Custom Branding unloaded. The asset routes stay until Home Assistant restarts"
    )
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Clean the frontend package even when the entry never reached LOADED.

    The core calls this on ConfigEntry.async_remove regardless of entry state,
    unlike async_unload_entry, which returns early for anything but LOADED. So
    a setup that failed mid-way still gets its on-disk changes reverted.
    """
    if restored := await _async_restore_html(hass):
        _LOGGER.info(
            "Restored %d original page(s) on removal: %s", len(restored), restored
        )


async def _async_restore_html(hass: HomeAssistant) -> list[str]:
    """Put the original pages back. Safe to call unconditionally."""
    try:
        root = await hass.async_add_executor_job(_frontend_root)
        return await hass.async_add_executor_job(html_patch.restore_titles, root)
    except Exception:  # noqa: BLE001
        _LOGGER.exception("Could not restore the original frontend pages")
        return []


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry when the options change."""
    await hass.config_entries.async_reload(entry.entry_id)


def _scan_assets(assets_dir: Path) -> set[str] | None:
    """List the files in the asset folder. Runs in the executor."""
    if not assets_dir.is_dir():
        return None
    return {entry.name for entry in assets_dir.iterdir() if entry.is_file()}


def _frontend_root() -> Path:
    """Locate the installed home-assistant-frontend package.

    Never hardcode this path: it carries the Python version of the image
    (already went from 3.13 to 3.14) and changes with every base image bump.
    """
    import hass_frontend  # noqa: PLC0415

    return Path(hass_frontend.where())


@callback
def _snapshot_manifest() -> dict[str, Any]:
    """Copy the frontend's original values once, before overwriting them.

    There is no public read API for the manifest, hence the defensive getattr:
    if the core ever renames this, the integration loses the restore instead of
    failing setup.
    """
    manifest = getattr(frontend, "MANIFEST_JSON", None)
    current = getattr(manifest, "manifest", None)
    if not isinstance(current, dict):
        _LOGGER.warning(
            "Could not read the frontend manifest: the PWA keys will only go "
            "back to their defaults after a Home Assistant restart"
        )
        return {}
    return {key: deepcopy(current[key]) for key in MANIFEST_KEYS if key in current}


@callback
def _restore_manifest(snapshot: dict[str, Any] | None) -> None:
    """Put the core PWA values back."""
    if not snapshot:
        return
    for key, value in snapshot.items():
        frontend.add_manifest_json_key(key, value)


@callback
def _apply_manifest(present: set[str], brand_name: str) -> None:
    """Rewrite the PWA name and icons, keeping both purposes."""
    icons: list[dict[str, str]] = []
    for size in MANIFEST_ANY_SIZES:
        name = f"favicon-{size}x{size}.png"
        if name in present:
            icons.append(_icon(name, size, "any"))
    for size in MANIFEST_MASKABLE_SIZES:
        name = f"maskable_icon-{size}x{size}.png"
        if name in present:
            icons.append(_icon(name, size, "maskable"))

    if not icons:
        # Writing an empty list would be worse than leaving the core icons, but
        # so is keeping the icons of a PREVIOUS asset folder after a reload, so
        # this branch is loud.
        _LOGGER.warning(
            "No manifest icon found: the installed app keeps whatever icons are "
            "currently set, which may belong to an earlier configuration"
        )
    else:
        if not any(icon["purpose"] == "maskable" for icon in icons):
            _LOGGER.warning(
                "No maskable_icon-*.png found: Android will fall back to a "
                "cropped version of the regular icon"
            )
        frontend.add_manifest_json_key("icons", icons)

    frontend.add_manifest_json_key("name", brand_name)
    frontend.add_manifest_json_key("short_name", brand_name)
    frontend.add_manifest_json_key("description", brand_name)
    frontend.add_manifest_json_key("screenshots", [])
    # Without these two, Chrome on Android offers the Home Assistant Companion
    # App from the Play Store instead of installing this PWA.
    frontend.add_manifest_json_key("prefer_related_applications", False)
    frontend.add_manifest_json_key("related_applications", [])
    # theme_color is deliberately left alone: the core theme handler rewrites it
    # on every theme change and would overwrite whatever we set here.


def _icon(name: str, size: int, purpose: str) -> dict[str, str]:
    """Build one manifest icon entry pointing at the served asset.

    Deliberately points at the integration's own prefix instead of the
    /static/icons override: /static/** is cached first-and-forever by the
    service worker, while this prefix falls into a 24h revalidating bucket, so
    a future logo change actually reaches installed apps.
    """
    return {
        "src": f"{ASSETS_URL}/{name}",
        "sizes": f"{size}x{size}",
        "type": "image/png",
        "purpose": purpose,
    }
