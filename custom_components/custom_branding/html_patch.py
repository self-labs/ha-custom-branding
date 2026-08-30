"""Rewrite the login and onboarding HTML shipped inside home-assistant-frontend.

Everything else this integration does goes through public APIs and never
touches the container. This module is the exception, and it exists for exactly
one reason: `authorize.html` and `onboarding.html` are static files with a
hardcoded `<title>Home Assistant</title>`, served by exact-match routes that
cannot be shadowed, and no template hook reaches them.

The icons on those pages do NOT need this: they are requested by URL
(`/static/icons/...`) and are already covered by the static routes registered
in `__init__.py`. This module only changes the window title, and only when the
user opts in.

Every function here does blocking disk I/O and must be called through
`hass.async_add_executor_job`.
"""

from __future__ import annotations

import gzip
import html
import logging
import os
import threading
from pathlib import Path

from .const import BACKUP_SUFFIX, HA_TITLE, PATCH_MARKER, PATCHED_HTML

_LOGGER = logging.getLogger(__name__)

# patch_titles and restore_titles are dispatched through
# hass.async_add_executor_job, which lands on a 64 thread pool. The restore
# action does not go through the config entry setup lock, so it can run while a
# reload triggered by apply is patching the very same files. Interleaved, one
# thread deletes a backup the other just recreated, leaving a marked file that
# _patch_one refuses to touch and restore_titles skips forever. A threading lock
# rather than an asyncio one, so the guarantee holds regardless of who calls.
_LOCK = threading.Lock()


def patch_titles(root: Path, brand_name: str) -> list[str]:
    """Replace the window title in the login and onboarding pages.

    Returns the names of the files actually rewritten.
    """
    patched: list[str] = []
    with _LOCK:
        for name in PATCHED_HTML:
            try:
                if _patch_one(root / name, brand_name):
                    patched.append(name)
            except OSError as err:
                _LOGGER.error("Could not rewrite %s: %s", root / name, err)
    return patched


def restore_titles(root: Path) -> list[str]:
    """Put the original HTML back from the sidecar backups."""
    restored: list[str] = []
    with _LOCK:
        for name in PATCHED_HTML:
            target = root / name
            backup = target.with_name(target.name + BACKUP_SUFFIX)
            if not backup.is_file():
                continue
            try:
                data = backup.read_bytes()
                _atomic_write(target, data)
                _refresh_sidecars(target, data)
                backup.unlink()
                restored.append(name)
            except OSError as err:
                _LOGGER.error("Could not restore %s: %s", target, err)
    return restored


def _patch_one(target: Path, brand_name: str) -> bool:
    if not target.is_file():
        _LOGGER.warning("Missing file, skipped: %s", target)
        return False

    backup = target.with_name(target.name + BACKUP_SUFFIX)
    current = target.read_text(encoding="utf-8")

    if PATCH_MARKER in current:
        # Patched on an earlier boot. Always start from the pristine copy, so a
        # changed brand name does not stack rewrites on top of each other.
        if not backup.is_file():
            _LOGGER.warning("Backup missing for %s, leaving it alone", target)
            return False
        source = backup.read_text(encoding="utf-8")
    else:
        # Pristine: either a fresh install or right after a "re-pull image".
        # Take the backup now, while the file is still original.
        source = current
        _atomic_write(backup, current.encode("utf-8"))

    patched = source.replace(
        f"<title>{HA_TITLE}</title>", f"<title>{html.escape(brand_name)}</title>"
    )
    if patched == source:
        _LOGGER.warning(
            "No <title> matched in %s. The frontend markup probably changed", target
        )
        return False

    patched = patched.replace("</head>", f"{PATCH_MARKER}</head>", 1)
    data = patched.encode("utf-8")
    _atomic_write(target, data)
    _refresh_sidecars(target, data)
    return True


def _refresh_sidecars(target: Path, data: bytes) -> None:
    """Regenerate the pre-compressed twins aiohttp serves with priority.

    Every HTML, SVG and XML file in the frontend package ships alongside a
    `.gz` and a `.br`. aiohttp checks those FIRST, so rewriting only the plain
    file means every real browser (which always sends
    `Accept-Encoding: gzip, br`) keeps receiving the original content.
    """
    gz = target.with_name(target.name + ".gz")
    if gz.is_file():
        _atomic_write(gz, gzip.compress(data, 9))

    br = target.with_name(target.name + ".br")
    if not br.is_file():
        return
    try:
        import brotli  # noqa: PLC0415
    except ImportError:
        # brotli is not a Home Assistant requirement. Deleting the stale sidecar
        # makes aiohttp fall back to .gz and then to the plain file, which is
        # correct; keeping it would serve the pre-patch page.
        br.unlink()
        _LOGGER.debug("brotli unavailable, removed %s", br)
    else:
        _atomic_write(br, brotli.compress(data, quality=11))


def _atomic_write(target: Path, data: bytes) -> None:
    """Write through a temp file in the same directory, then rename.

    The temp name carries the thread id: a fixed name is shared by every writer
    of the same target, so one thread could rename bytes another was still
    writing. It also keeps a leftover from an earlier crash out of the way.
    """
    tmp = target.with_name(f"{target.name}.{threading.get_ident()}.custom_branding-tmp")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, target)
    finally:
        tmp.unlink(missing_ok=True)
