"""Config flow for Nexprint."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NexprintApiClient, NexprintApiError, NexprintAuthError
from .const import (
    AUTH_MODE_PASSWORD,
    AUTH_MODE_TOKEN,
    CONF_ACCEPT_TERMS,
    CONF_ACCESS_TOKEN,
    CONF_AUTH_MODE,
    CONF_EMAIL,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)


class NexprintConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Nexprint."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Let the user choose Email/Password or Token login."""
        return self.async_show_menu(
            step_id="user",
            menu_options=["password", "token"],
        )

    async def async_step_password(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Authenticate using Elegoo/Nexprint Email + Password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input.get(CONF_ACCEPT_TERMS):
                errors[CONF_ACCEPT_TERMS] = "terms_not_accepted"
            else:
                email = user_input[CONF_EMAIL].strip()
                password = user_input[CONF_PASSWORD]
                client = NexprintApiClient(
                    async_get_clientsession(self.hass),
                    email=email,
                    password=password,
                )
                try:
                    access_token, refresh_token = (
                        await client.async_login_with_password()
                    )
                    account = await client.async_get_account_data()
                except NexprintAuthError:
                    errors["base"] = "invalid_auth"
                except NexprintApiError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(f"user:{account.user_id}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Nexprint ({account.nickname})",
                        data={
                            CONF_AUTH_MODE: AUTH_MODE_PASSWORD,
                            CONF_EMAIL: email,
                            CONF_PASSWORD: password,
                            CONF_ACCEPT_TERMS: True,
                            CONF_ACCESS_TOKEN: access_token,
                            CONF_REFRESH_TOKEN: refresh_token or "",
                            CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_EMAIL): str,
                vol.Required(CONF_PASSWORD): str,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_MINUTES
                ): vol.All(int, vol.Range(min=5, max=1440)),
                vol.Required(CONF_ACCEPT_TERMS, default=False): bool,
            }
        )
        return self.async_show_form(
            step_id="password", data_schema=schema, errors=errors
        )

    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Authenticate using an access_token (and optional refresh_token)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            if not user_input.get(CONF_ACCEPT_TERMS):
                errors[CONF_ACCEPT_TERMS] = "terms_not_accepted"
            else:
                access_token = user_input[CONF_ACCESS_TOKEN].strip()
                refresh_token = user_input.get(CONF_REFRESH_TOKEN, "").strip()
                client = NexprintApiClient(
                    async_get_clientsession(self.hass),
                    access_token=access_token,
                    refresh_token=refresh_token or None,
                )
                try:
                    account = await client.async_get_account_data()
                except NexprintAuthError:
                    errors["base"] = "invalid_auth"
                except NexprintApiError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(f"user:{account.user_id}")
                    self._abort_if_unique_id_configured()
                    return self.async_create_entry(
                        title=f"Nexprint ({account.nickname})",
                        data={
                            CONF_AUTH_MODE: AUTH_MODE_TOKEN,
                            CONF_ACCEPT_TERMS: True,
                            CONF_ACCESS_TOKEN: client.access_token or access_token,
                            CONF_REFRESH_TOKEN: client.refresh_token or refresh_token,
                            CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                        },
                    )

        schema = vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN): str,
                vol.Optional(CONF_REFRESH_TOKEN, default=""): str,
                vol.Required(
                    CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL_MINUTES
                ): vol.All(int, vol.Range(min=5, max=1440)),
                vol.Required(CONF_ACCEPT_TERMS, default=False): bool,
            }
        )
        return self.async_show_form(step_id="token", data_schema=schema, errors=errors)

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication when session tokens expire."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Re-authenticate an existing Nexprint config entry."""
        reauth_entry = self._get_reauth_entry()
        if reauth_entry.data.get(CONF_AUTH_MODE) == AUTH_MODE_TOKEN:
            return await self.async_step_token(user_input)
        return await self.async_step_password(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler."""
        return NexprintOptionsFlow()


class NexprintOptionsFlow(OptionsFlow):
    """Handle Nexprint options updates."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage polling interval options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**self.config_entry.data, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_SCAN_INTERVAL,
                    default=current.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
                    ),
                ): vol.All(int, vol.Range(min=5, max=1440)),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
