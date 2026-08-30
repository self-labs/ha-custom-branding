"""Config flow for Custom Branding."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import (
    ASSET_ROUTES,
    CONF_ASSETS_DIR,
    CONF_BRAND_NAME,
    CONF_PATCH_HTML,
    DEFAULT_ASSETS_DIR,
    DOMAIN,
)


def _schema(defaults: dict[str, Any]) -> vol.Schema:
    """Build the form, shared by the config and the options flow."""
    return vol.Schema(
        {
            vol.Required(
                CONF_BRAND_NAME, default=defaults.get(CONF_BRAND_NAME, "")
            ): selector.TextSelector(),
            vol.Required(
                CONF_ASSETS_DIR,
                default=defaults.get(CONF_ASSETS_DIR, DEFAULT_ASSETS_DIR),
            ): selector.TextSelector(),
            vol.Required(
                CONF_PATCH_HTML, default=defaults.get(CONF_PATCH_HTML, False)
            ): selector.BooleanSelector(),
        }
    )


def _validate(hass_config_path: str, user_input: dict[str, Any]) -> dict[str, str]:
    """Check the asset folder. Runs in the executor: it touches the disk."""
    errors: dict[str, str] = {}

    name = user_input[CONF_BRAND_NAME].strip()
    if not name:
        errors[CONF_BRAND_NAME] = "empty_name"

    raw = user_input[CONF_ASSETS_DIR].strip().strip("/")
    if not raw:
        errors[CONF_ASSETS_DIR] = "empty_dir"
        return errors
    if ".." in Path(raw).parts:
        errors[CONF_ASSETS_DIR] = "unsafe_dir"
        return errors

    folder = Path(hass_config_path) / raw
    if not folder.is_dir():
        errors[CONF_ASSETS_DIR] = "dir_not_found"
        return errors

    present = {entry.name for entry in folder.iterdir() if entry.is_file()}
    if not present & set(ASSET_ROUTES):
        errors[CONF_ASSETS_DIR] = "no_assets"

    return errors


class CustomBrandingConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Ask for the brand name and where the artwork lives."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self.hass.async_add_executor_job(
                _validate, self.hass.config.config_dir, user_input
            )
            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_BRAND_NAME].strip(),
                    data={},
                    options={
                        CONF_BRAND_NAME: user_input[CONF_BRAND_NAME].strip(),
                        CONF_ASSETS_DIR: user_input[CONF_ASSETS_DIR].strip().strip("/"),
                        CONF_PATCH_HTML: user_input[CONF_PATCH_HTML],
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_schema(user_input or {}),
            errors=errors,
            description_placeholders={"default_dir": DEFAULT_ASSETS_DIR},
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> CustomBrandingOptionsFlow:
        """Return the options flow."""
        return CustomBrandingOptionsFlow()


class CustomBrandingOptionsFlow(OptionsFlow):
    """Edit the settings after setup.

    Note the empty constructor: `OptionsFlow` only exposes `config_entry` as a
    read-only property from 2024.12 onwards, the release that also deprecated
    assigning it (the setter was removed in 2025.12). That is why the HACS floor
    is 2024.12 and not 2024.7: on 2024.11 and older the base class has no
    `config_entry` at all and `async_step_init` would raise AttributeError.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show the same form, pre-filled with the current values."""
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = await self.hass.async_add_executor_job(
                _validate, self.hass.config.config_dir, user_input
            )
            if not errors:
                return self.async_create_entry(
                    data={
                        CONF_BRAND_NAME: user_input[CONF_BRAND_NAME].strip(),
                        CONF_ASSETS_DIR: user_input[CONF_ASSETS_DIR].strip().strip("/"),
                        CONF_PATCH_HTML: user_input[CONF_PATCH_HTML],
                    }
                )

        current = dict(self.config_entry.options)
        return self.async_show_form(
            step_id="init",
            data_schema=_schema(user_input or current),
            errors=errors,
            description_placeholders={"default_dir": DEFAULT_ASSETS_DIR},
        )
