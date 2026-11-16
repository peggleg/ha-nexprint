"""DataUpdateCoordinator for Nexprint."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    NexprintAccountData,
    NexprintApiClient,
    NexprintApiError,
    NexprintAuthError,
)
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL_MINUTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class NexprintCoordinator(DataUpdateCoordinator[NexprintAccountData]):
    """Coordinator polling Nexprint account profile and message state."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: NexprintApiClient,
    ) -> None:
        self.client = client
        interval_minutes = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(minutes=int(interval_minutes)),
        )

    async def _async_update_data(self) -> NexprintAccountData:
        """Fetch latest profile and notification state."""
        try:
            data = await self.client.async_get_account_data()
        except NexprintAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except NexprintApiError as err:
            raise UpdateFailed(str(err)) from err

        if (
            self.client.access_token != self.config_entry.data.get(CONF_ACCESS_TOKEN)
            or self.client.refresh_token
            != self.config_entry.data.get(CONF_REFRESH_TOKEN)
        ):
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data={
                    **self.config_entry.data,
                    CONF_ACCESS_TOKEN: self.client.access_token or "",
                    CONF_REFRESH_TOKEN: self.client.refresh_token or "",
                },
            )

        return data
