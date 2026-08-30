"""Constants for the Custom Branding integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "custom_branding"

# Config entry options.
CONF_BRAND_NAME: Final = "brand_name"
CONF_ASSETS_DIR: Final = "assets_dir"
CONF_PATCH_HTML: Final = "patch_html"

DEFAULT_BRAND_NAME: Final = "Home Assistant"
# Relative to the config directory. Deliberately outside custom_components/:
# HACS replaces the integration folder on every update, which would wipe the
# user's own artwork.
DEFAULT_ASSETS_DIR: Final = DOMAIN

# Public URL prefix for the user's asset folder. Kept off /static/ on purpose:
# the service worker caches /static/** first-and-forever, while anything else
# falls into a 24h stale-while-revalidate bucket.
ASSETS_URL: Final = f"/{DOMAIN}-assets"
MODULE_URL: Final = f"/{DOMAIN}-module"
JS_URL: Final = f"{MODULE_URL}/branding.js"

# File name in the user's asset folder -> URL the frontend actually requests.
#
# Registering one route per FILE is what makes this work: aiohttp resolves by
# longest matching prefix, so "/static/icons/favicon.ico" wins over the
# frontend's "/static" StaticResource no matter which was registered first.
# Registering the DIRECTORY "/static/icons" instead would shadow the whole
# subtree and 404 every file we do not ship.
ASSET_ROUTES: Final[dict[str, str]] = {
    "favicon.ico": "/static/icons/favicon.ico",
    "favicon-16x16.png": "/static/icons/favicon-16x16.png",
    "favicon-32x32.png": "/static/icons/favicon-32x32.png",
    "favicon-192x192.png": "/static/icons/favicon-192x192.png",
    "favicon-384x384.png": "/static/icons/favicon-384x384.png",
    "favicon-512x512.png": "/static/icons/favicon-512x512.png",
    "favicon-1024x1024.png": "/static/icons/favicon-1024x1024.png",
    "favicon-apple-180x180.png": "/static/icons/favicon-apple-180x180.png",
    "mask-icon.svg": "/static/icons/mask-icon.svg",
    "maskable_icon-48x48.png": "/static/icons/maskable_icon-48x48.png",
    "maskable_icon-72x72.png": "/static/icons/maskable_icon-72x72.png",
    "maskable_icon-96x96.png": "/static/icons/maskable_icon-96x96.png",
    "maskable_icon-128x128.png": "/static/icons/maskable_icon-128x128.png",
    "maskable_icon-192x192.png": "/static/icons/maskable_icon-192x192.png",
    "maskable_icon-384x384.png": "/static/icons/maskable_icon-384x384.png",
    "maskable_icon-512x512.png": "/static/icons/maskable_icon-512x512.png",
    "logo-loading.svg": "/static/images/home-assistant-logo-loading.svg",
    "footer-light.svg": "/static/images/open-home-foundation-on-light.svg",
    "footer-dark.svg": "/static/images/open-home-foundation-on-dark.svg",
}

# Files that take over the route of another asset when present, overriding the
# entry above for that URL.
#
# The login and onboarding screens render `favicon-192x192.png` as a 56x56
# `img`, on a background that is #fafafa in the light theme and #111111 in the
# dark one. A PNG cannot follow that: a light glyph disappears on one, a dark
# glyph on the other, and an opaque background becomes a bright square floating
# in the dark theme.
#
# An SVG can, through `@media (prefers-color-scheme: dark)` inside the file.
# aiohttp picks the Content-Type from the file ON DISK, not from the URL, so an
# SVG served at the .png route arrives as image/svg+xml and the browser renders
# it as SVG. The manifest keeps pointing at the real PNG through ASSETS_URL,
# because a PWA icon has to be a bitmap.
ASSET_OVERRIDES: Final[dict[str, str]] = {
    "login-icon.svg": "/static/icons/favicon-192x192.png",
}

# The manifest ships 4 "any" icons and 7 "maskable" ones. add_manifest_json_key
# replaces the whole array, so both groups have to be rebuilt together or the
# adaptive icon disappears on Android.
MANIFEST_ANY_SIZES: Final = (192, 384, 512, 1024)
MANIFEST_MASKABLE_SIZES: Final = (48, 72, 96, 128, 192, 384, 512)

# HTML files served straight off disk. No template hook exists for these, and
# they cannot be shadowed by a route either: both are exact-match resources
# already registered by the frontend.
PATCHED_HTML: Final = ("authorize.html", "onboarding.html")

HA_TITLE: Final = "Home Assistant"
PATCH_MARKER: Final = "<!--custom_branding-->"
BACKUP_SUFFIX: Final = ".custom_branding-orig"

SERVICE_APPLY: Final = "apply"
SERVICE_RESTORE: Final = "restore"

DATA_UNDO_JS: Final = "undo_js"
DATA_PATCHED: Final = "patched_html"
DATA_ROUTES: Final = "routes"
DATA_MANIFEST_SNAPSHOT: Final = "manifest_snapshot"

# Every key _apply_manifest writes. All seven exist in the core default manifest,
# so restoring from a snapshot leaves nothing behind. theme_color is deliberately
# absent: the core theme handler rewrites that one on its own.
MANIFEST_KEYS: Final = (
    "icons",
    "name",
    "short_name",
    "description",
    "screenshots",
    "prefer_related_applications",
    "related_applications",
)
