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
from pathlib import Path
from typing import Any
from urllib.parse import quote

import voluptuous as vol

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from . import html_patch
from .const import (
    ASSET_ROUTES,
    ASSETS_URL,
    CONF_ASSETS_DIR,
    CONF_BRAND_NAME,
    CONF_PATCH_HTML,
    DATA_PATCHED,
    DEFAULT_ASSETS_DIR,
    DEFAULT_BRAND_NAME,
    DOMAIN,
    JS_URL,
    MANIFEST_ANY_SIZES,
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
        root = await hass.async_add_executor_job(_frontend_root)
        restored = await hass.async_add_executor_job(html_patch.restore_titles, root)
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

    present = await hass.async_add_executor_job(_scan_assets, assets_dir)
    if present is None:
        raise HomeAssistantError(
            f"Asset folder not found: {assets_dir}. Create it and put your "
            f"icons there, then reload the integration."
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
    # Registering the same URL twice raises (or is silently ignored, depending
    # on what else got registered in between), and there is no public API to
    # remove a route. So this runs once per Home Assistant start; reloading the
    # entry re-applies everything else but keeps the routes already in place.
    registered: set[str] = hass.data.setdefault(DOMAIN, {}).setdefault("routes", set())
    configs: list[StaticPathConfig] = []

    if ASSETS_URL not in registered:
        configs.append(StaticPathConfig(ASSETS_URL, str(assets_dir), False))
        registered.add(ASSETS_URL)
    if MODULE_URL not in registered:
        configs.append(
            StaticPathConfig(MODULE_URL, str(Path(__file__).parent / "frontend"), False)
        )
        registered.add(MODULE_URL)

    for filename in sorted(usable):
        url = ASSET_ROUTES[filename]
        if url in registered:
            continue
        configs.append(StaticPathConfig(url, str(assets_dir / filename), True))
        registered.add(url)

    if configs:
        await hass.http.async_register_static_paths(configs)
        _LOGGER.info("Serving %d branded asset(s) from %s", len(usable), assets_dir)

    # --- Layer 2: PWA manifest and the tab title -------------------------
    _apply_manifest(usable, brand_name)
    # The brand name travels in the query string so the module needs no build
    # step. Keep the exact URL around: remove_extra_js_url matches by string,
    # and the core stores these in a frozenset.
    js_url = f"{JS_URL}?brand={quote(brand_name, safe='')}"
    frontend.add_extra_js_url(hass, js_url)
    hass.data[DOMAIN][DATA_UNDO_JS] = js_url

    # --- Layer 3: opt-in HTML patch --------------------------------------
    if options.get(CONF_PATCH_HTML):
        root = await hass.async_add_executor_job(_frontend_root)
        patched = await hass.async_add_executor_job(
            html_patch.patch_titles, root, brand_name
        )
        hass.data[DOMAIN][DATA_PATCHED] = patched
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
    if js_url := hass.data.get(DOMAIN, {}).pop(DATA_UNDO_JS, None):
        frontend.remove_extra_js_url(hass, js_url)

    if hass.data.get(DOMAIN, {}).get(DATA_PATCHED):
        root = await hass.async_add_executor_job(_frontend_root)
        await hass.async_add_executor_job(html_patch.restore_titles, root)
        hass.data[DOMAIN][DATA_PATCHED] = []

    _LOGGER.info(
        "Custom Branding unloaded. The asset routes stay until Home Assistant restarts"
    )
    return True


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

    if icons:
        if not any(icon["purpose"] == "maskable" for icon in icons):
            _LOGGER.warning(
                "No maskable_icon-*.png found: Android will fall back to a "
                "cropped version of the regular icon"
            )
        frontend.add_manifest_json_key("icons", icons)
    else:
        _LOGGER.warning("No manifest icon found, keeping the Home Assistant ones")

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
