"""
Support for Somfy Smart Thermostat.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/climate.somfy/
"""
import time
from typing import Optional, List

from ..pymfy.api.devices.category import Category
from ..pymfy.api.devices.thermostat import Thermostat, TargetMode, DurationType, RegulationState

from homeassistant.components.climate import ClimateDevice
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE, ATTR_BATTERY_LEVEL, ATTR_MODE
from homeassistant.components.climate.const import (
    HVAC_MODE_HEAT,
    HVAC_MODE_AUTO,
    PRESET_AWAY,
    PRESET_HOME,
    PRESET_NONE,
    PRESET_SLEEP,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_IDLE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_PRESET_MODE,
)
from homeassistant.components.somfy import DOMAIN, SomfyEntity, DEVICES, API
from .const import (
    ATTR_REGULATION,
    PRESET_ANTI_FREEZE,
)
import logging

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Somfy climate platform."""

    def get_thermostats():
        """Retrieve thermostats."""
        categories = {Category.HVAC.value}

        devices = hass.data[DOMAIN][DEVICES]

        return [
            SomfyClimate(climate, hass.data[DOMAIN][API])
            for climate in devices
            if categories & set(climate.categories)
        ]

    async_add_entities(await hass.async_add_executor_job(get_thermostats), True)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Old way of setting up platform.

    Can only be called when a user accidentally mentions the platform in their
    config. But even in that case it would have been ignored.
    """
    pass


class SomfyClimate(SomfyEntity, ClimateDevice):
    """Representation of a Somfy smart thermostat"""

    def __init__(self, device, api):
        """Initialize the Somfy device."""
        super().__init__(device, api)
        self.climate = Thermostat(self.device, self.api)
        self._regulation_state = self.climate.get_regulation_state()
        if self._regulation_state == RegulationState.TIMETABLE.value:
            self._hvac_mode = HVAC_MODE_AUTO
        elif self._regulation_state == RegulationState.DEROGATION.value:
            self._hvac_mode = HVAC_MODE_HEAT
        self._target_mode = self.climate.get_target_mode()
        if self._target_mode == TargetMode.AT_HOME.value:
            self._preset_mode = PRESET_HOME
        elif self._target_mode == TargetMode.AWAY.value:
            self._preset_mode = PRESET_AWAY
        elif self._target_mode == TargetMode.SLEEP.value:
            self._preset_mode = PRESET_SLEEP
        elif self._target_mode == TargetMode.FROST_PROTECTION.value:
            self._preset_mode = PRESET_ANTI_FREEZE
        else:
            self._preset_mode = PRESET_NONE
        self._target_temperature = self.climate.get_target_temperature()
        self._away_temp = self.climate.get_away_temperature()
        self._at_home_temp = self.climate.get_at_home_temperature()

    async def async_update(self):
        """Update the device with the latest data."""
        await super().async_update()
        self.climate = Thermostat(self.device, self.api)
        self._regulation_state = self.climate.get_regulation_state()
        if self._regulation_state == RegulationState.TIMETABLE.value:
            self._hvac_mode = HVAC_MODE_AUTO
        elif self._regulation_state == RegulationState.DEROGATION.value:
            self._hvac_mode = HVAC_MODE_HEAT
        self._target_mode = self.climate.get_target_mode()
        if self._target_mode == TargetMode.AT_HOME.value:
            self._preset_mode = PRESET_HOME
        elif self._target_mode == TargetMode.AWAY.value:
            self._preset_mode = PRESET_AWAY
        elif self._target_mode == TargetMode.SLEEP.value:
            self._preset_mode = PRESET_SLEEP
        elif self._target_mode == TargetMode.FROST_PROTECTION.value:
            self._preset_mode = PRESET_ANTI_FREEZE
        else:
            self._preset_mode = PRESET_NONE
        self._target_temperature = self.climate.get_target_temperature()
    
    @property
    def hvac_action(self):
        """Return the current running hvac operation if supported.

        Need to be one of CURRENT_HVAC_*.
        """
        if self.current_temperature > self.target_temperature:
            return CURRENT_HVAC_IDLE
        return CURRENT_HVAC_HEAT

    @property
    def temperature_unit(self) -> str:
        return TEMP_CELSIUS

    @property
    def current_temperature(self) -> Optional[float]:
        """Return the current temperature."""
        return self.climate.get_ambient_temperature()

    @property
    def current_humidity(self) -> Optional[int]:
        """Return the current humidity."""
        return int(self.climate.get_humidity())

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def hvac_mode(self) -> str:
        """Return current operation."""
        return self._hvac_mode

    @property
    def hvac_modes(self) -> List[str]:
        return [HVAC_MODE_HEAT, HVAC_MODE_AUTO]

    @property
    def preset_mode(self) -> Optional[str]:
        return self._preset_mode

    @property
    def preset_modes(self) -> Optional[List[str]]:
        return [PRESET_NONE, PRESET_AWAY, PRESET_HOME, PRESET_ANTI_FREEZE, PRESET_SLEEP]

    async def _async_set_target(self, mode, temperature):
        _LOGGER.warning(
            "\nSet Target:\n"
            + "\t"
            + self._regulation_state
            + "\n"
            + "\t"
            + mode
            + "\n"
            + "\t"
            + str(temperature)
        )
        self.climate.set_target(
            mode, temperature, DurationType.FURTHER_NOTICE, 60
        )
        time.sleep(20)

    async def async_set_temperature(self, **kwargs) -> None:
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return
        self._hvac_mode = HVAC_MODE_HEAT
        self._preset_mode = PRESET_NONE
        await self._async_set_target(TargetMode.MANUEL, temperature)

    async def async_set_hvac_mode(self, hvac_mode: str) -> None:
        self._preset_mode = PRESET_NONE
        if hvac_mode == HVAC_MODE_HEAT:
            self._hvac_mode = HVAC_MODE_HEAT
            await self._async_set_target(TargetMode.MANUEL, self._target_temperature)
        elif hvac_mode == HVAC_MODE_AUTO:
            self._hvac_mode = HVAC_MODE_AUTO
            self.climate.cancel_target()
        else:
            _LOGGER.error("Unrecognized hvac mode: %s", hvac_mode)
            return

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        if preset_mode not in self.preset_modes:
            _LOGGER.error(
                "Preset " + preset_mode + " is not available for " + self._name
            )
            return

        mode = {
            PRESET_NONE: {"mode": "manuel", "temperature": None},
            PRESET_AWAY: {"mode": "away", "temperature": self.climate.get_away_temperature()},
            PRESET_HOME: {"mode": "at_home", "temperature": self.climate.get_at_home_temperature()},
            PRESET_ANTI_FREEZE: {"mode": "frost_protection", "temperature": self.climate.get_frost_protection_temperature()},
            PRESET_SLEEP: {"mode": "sleep", "temperature": self.climate.get_night_temperature()},
        }
        self._hvac_mode = HVAC_MODE_HEAT

        await self._async_set_target(**mode[preset_mode])

    @property
    def supported_features(self) -> int:
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_PRESET_MODE

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attr = {ATTR_BATTERY_LEVEL: self.climate.get_battery(),
                ATTR_MODE: self._target_mode,
                ATTR_REGULATION: self._regulation_state}
        return attr
