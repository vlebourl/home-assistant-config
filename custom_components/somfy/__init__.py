"""
Support for Somfy hubs.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/somfy/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol
from requests import HTTPError

from homeassistant.helpers import config_validation as cv, config_entry_oauth2_flow
from homeassistant.components.somfy import config_flow
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import Throttle

from . import api

API = "api"

DEVICES = "devices"

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=30)

DOMAIN = "somfy"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"

SOMFY_AUTH_CALLBACK_PATH = "/auth/somfy/callback"
SOMFY_AUTH_START = "/auth/somfy"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)

SOMFY_COMPONENTS = ["cover", "climate"]


async def async_setup(hass, config):
    """Set up the Somfy component."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    config_flow.SomfyFlowHandler.async_register_implementation(
        hass,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            "https://accounts.somfy.com/oauth/oauth/v2/auth",
            "https://accounts.somfy.com/oauth/oauth/v2/token",
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Somfy from a config entry."""
    # Backwards compat
    if "auth_implementation" not in entry.data:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "auth_implementation": DOMAIN}
        )

    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )

    hass.data[DOMAIN][API] = api.ConfigEntrySomfyApi(hass, entry, implementation)

    await update_all_devices(hass)

    for component in SOMFY_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(API, None)
    await asyncio.gather(
        *[
            hass.config_entries.async_forward_entry_unload(entry, component)
            for component in SOMFY_COMPONENTS
        ]
    )
    return True


class SomfyEntity(Entity):
    """Representation of a generic Somfy device."""

    def __init__(self, device, somfy_api):
        """Initialize the Somfy device."""
        self.device = device
        self.api = somfy_api

    @property
    def unique_id(self):
        """Return the unique id base on the id returned by Somfy."""
        return self.device.id

    @property
    def name(self):
        """Return the name of the device."""
        return self.device.name

    @property
    def device_info(self):
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "model": self.device.type,
            "via_hub": (DOMAIN, self.device.site_id),
            # For the moment, Somfy only returns their own device.
            "manufacturer": "Somfy",
        }

    async def async_update(self):
        """Update the device with the latest data."""
        await update_all_devices(self.hass)
        devices = self.hass.data[DOMAIN][DEVICES]
        self.device = next((d for d in devices if d.id == self.device.id), self.device)

    def has_capability(self, capability):
        """Test if device has a capability."""
        capabilities = self.device.capabilities
        return bool([c for c in capabilities if c.name == capability])


@Throttle(SCAN_INTERVAL)
async def update_all_devices(hass):
    """Update all the devices."""
    try:
        data = hass.data[DOMAIN]
        data[DEVICES] = await hass.async_add_executor_job(data[API].get_devices)
    except HTTPError as err:
        _LOGGER.warning("Cannot update devices: %s", err.response.status_code)
