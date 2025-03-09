"""Support for media players through the SmartThings cloud API."""

from __future__ import annotations

import logging

from pysmartthings import Attribute, Capability, Command, SmartThings

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FullDevice, SmartThingsConfigEntry
from .const import MAIN
from .entity import SmartThingsEntity

_LOGGER = logging.getLogger(__name__)


CAPABILITIES = (
    Capability.AUDIO_MUTE,
    Capability.AUDIO_VOLUME,
    Capability.MEDIA_PLAYBACK,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SmartThingsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add covers for a config entry."""
    entry_data = entry.runtime_data
    async_add_entities(
        SmartThingsMediaPlayer(
            entry_data.client, device, entry_data.rooms
        )
        for device in entry_data.devices.values()
        if any(capability in CAPABILITIES for capability in device.status[MAIN])
    )


class SmartThingsMediaPlayer(SmartThingsEntity, MediaPlayerEntity):
    """Define a SmartThings media player."""

    def __init__(
        self,
        client: SmartThings,
        device: FullDevice,
        rooms: dict[str, str],
    ) -> None:
        """Initialize the media player class."""
        super().__init__(
            client,
            device,
            rooms,
            {
                Capability.AUDIO_MUTE,
                Capability.AUDIO_VOLUME,
                Capability.MEDIA_PLAYBACK,
            },
        )
        self._attr_name = "Media player"

        caps = MediaPlayerEntityFeature(0)

        if self.supports_capability(Capability.AUDIO_MUTE):
            caps |= MediaPlayerEntityFeature.VOLUME_MUTE

        if self.supports_capability(Capability.AUDIO_VOLUME):
            caps |= MediaPlayerEntityFeature.VOLUME_SET

        if self.supports_capability(Capability.MEDIA_PLAYBACK):
            for command in self.get_attribute_value(
                Capability.MEDIA_PLAYBACK, Attribute.SUPPORTED_PLAYBACK_COMMANDS
            ):
                match command:
                    case "play":
                        caps |= MediaPlayerEntityFeature.PLAY
                    case "pause":
                        caps |= MediaPlayerEntityFeature.PAUSE
                    case "stop":
                        caps |= MediaPlayerEntityFeature.STOP
                    case x:
                        _LOGGER.debug(
                            "Unsupported playback command %r for entity %s",
                            x,
                            self.entity_id,
                        )

        self._attr_supported_features = caps

    def _update_attr(self) -> None:
        if self.supports_capability(Capability.AUDIO_MUTE):
            match self.get_attribute_value(Capability.AUDIO_MUTE, Attribute.MUTE):
                case "muted":
                    is_muted = True
                case "unmuted":
                    is_muted = False
                case x:
                    _LOGGER.warning(
                        "Unknown mute state %r for entity %s", x, self.entity_id
                    )
                    is_muted = None

            self._attr_is_volume_muted = is_muted

        if self.supports_capability(
            Capability.AUDIO_VOLUME
        ):  # SmartThings uses 0..100, HA uses 0..1
            self._attr_volume_level = (
                self.get_attribute_value(Capability.AUDIO_VOLUME, Attribute.VOLUME)
                / 100
            )
            self._attr_volume_step = 0.01

        if self.supports_capability(Capability.MEDIA_PLAYBACK):
            match self.get_attribute_value(
                Capability.MEDIA_PLAYBACK, Attribute.PLAYBACK_STATUS
            ):
                case "paused":
                    state = MediaPlayerState.PAUSED
                case (
                    "playing" | "fast forwarding" | "rewinding"
                ):  # HA does not define separate states for these
                    state = MediaPlayerState.PLAYING
                case "stopped":
                    state = MediaPlayerState.IDLE
                case "buffering":
                    state = MediaPlayerState.BUFFERING
                case x:
                    _LOGGER.warning(
                        "Unknown playback state %r for entity %s", x, self.entity_id
                    )
                    state = None

            self._attr_state = state

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute the volume."""
        await self.execute_device_command(
            Capability.AUDIO_MUTE,
            Command.SET_MUTE,
            argument="muted" if mute else "unmuted",
        )

    async def async_set_volume_level(self, volume: float) -> None:
        """Set volume level, range 0..1."""
        await self.execute_device_command(
            Capability.AUDIO_VOLUME, Command.SET_VOLUME, argument=int(volume * 100)
        )

    async def async_media_play(self) -> None:
        """Send play command."""
        await self.execute_device_command(Capability.MEDIA_PLAYBACK, Command.PLAY)

    async def async_media_pause(self) -> None:
        """Send pause command."""
        await self.execute_device_command(Capability.MEDIA_PLAYBACK, Command.PAUSE)

    async def async_media_stop(self) -> None:
        """Send stop command."""
        await self.execute_device_command(Capability.MEDIA_PLAYBACK, Command.STOP)
