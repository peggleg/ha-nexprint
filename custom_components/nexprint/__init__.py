"""The Nexprint integration."""

from __future__ import annotations

from typing import TypeAlias

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import NexprintApiClient, NexprintApiError
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_EMAIL,
    CONF_KEYWORD,
    CONF_PAGE_SIZE,
    CONF_PASSWORD,
    CONF_REFRESH_TOKEN,
    DEFAULT_PAGE_SIZE,
    DOMAIN,
    EVENT_SEARCH_RESULTS,
    SERVICE_SEARCH,
)
from .coordinator import NexprintCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

NexprintConfigEntry: TypeAlias = ConfigEntry[NexprintCoordinator]

SERVICE_SEARCH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_KEYWORD): str,
        vol.Optional(CONF_PAGE_SIZE, default=DEFAULT_PAGE_SIZE): vol.All(
            int, vol.Range(min=1, max=100)
        ),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: NexprintConfigEntry) -> bool:
    """Set up Nexprint from a config entry."""
    client = NexprintApiClient(
        async_get_clientsession(hass),
        email=entry.data.get(CONF_EMAIL),
        password=entry.data.get(CONF_PASSWORD),
        access_token=entry.data.get(CONF_ACCESS_TOKEN),
        refresh_token=entry.data.get(CONF_REFRESH_TOKEN),
    )
    coordinator = NexprintCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _async_register_services(hass)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: NexprintConfigEntry
) -> None:
    """Reload the config entry when options are updated."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_register_services(hass: HomeAssistant) -> None:
    """Register domain-level Nexprint services once."""
    if hass.services.has_service(DOMAIN, SERVICE_SEARCH):
        return

    async def handle_search(call: ServiceCall) -> None:
        loaded_entries = hass.config_entries.async_loaded_entries(DOMAIN)
        if loaded_entries:
            client = loaded_entries[0].runtime_data.client
        else:
            client = NexprintApiClient(async_get_clientsession(hass))

        try:
            result = await client.async_search_models(
                keyword=call.data[CONF_KEYWORD],
                page_size=call.data[CONF_PAGE_SIZE],
            )
        except NexprintApiError as err:
            raise HomeAssistantError(str(err)) from err

        hass.bus.async_fire(
            EVENT_SEARCH_RESULTS,
            {
                "keyword": result.keyword,
                "total": result.total,
                "models": [
                    {
                        "id": m.public_id,
                        "title": m.title,
                        "author": m.author,
                        "url": m.url,
                        "downloads": m.downloads,
                        "likes": m.likes,
                    }
                    for m in result.models[:10]
                ],
            },
        )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SEARCH,
        handle_search,
        schema=SERVICE_SEARCH_SCHEMA,
    )


async def async_unload_entry(hass: HomeAssistant, entry: NexprintConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    other_loaded = [
        e
        for e in hass.config_entries.async_loaded_entries(DOMAIN)
        if e.entry_id != entry.entry_id
    ]
    if unload_ok and not other_loaded:
        hass.services.async_remove(DOMAIN, SERVICE_SEARCH)
    return unload_ok
