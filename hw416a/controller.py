"""High level control abstraction for the HW416A module.

This module contains a :class:`HW416AController` that encapsulates the wiring
of a typical HW416A breakout board when it is connected to the GPIO header of a
Raspberry Pi.  The class hides the raw `RPi.GPIO` calls and exposes Python
methods that match the common operations mentioned in the HW416A data sheet such
as powering the board on/off, switching the modulation mode and issuing trigger
pulses.

The implementation is intentionally defensive so that it can be used in unit
tests on non‑Raspberry Pi hosts.  You can inject a GPIO compatible module (or a
mock) by passing it to the constructor.  When running on the Pi the class will
fall back to the :mod:`RPi.GPIO` module automatically.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Callable, Mapping, Optional

try:  # pragma: no cover - optional dependency, covered by tests via injection
    import RPi.GPIO as _rpi_gpio
except ModuleNotFoundError:  # pragma: no cover - handled in __init__
    _rpi_gpio = None

LOGGER = logging.getLogger(__name__)


class GPIOConfigurationError(RuntimeError):
    """Raised when the controller cannot configure the GPIO subsystem."""


@dataclass(frozen=True)
class PinAssignment:
    """Named collection of pins used by the controller."""

    power_enable: int
    mode_select: int
    trigger: int
    status: int

    def as_mapping(self) -> Mapping[str, int]:
        return {
            "power_enable": self.power_enable,
            "mode_select": self.mode_select,
            "trigger": self.trigger,
            "status": self.status,
        }


class HW416AController:
    """High level wrapper around the GPIO interface of a HW416A module.

    Parameters
    ----------
    pin_assignment:
        Optional overrides for the default BCM pin mapping.  The defaults map
        the hardware pins to the following BCM pins: power enable = 17, mode
        select = 27, trigger = 22, status = 23.
    gpio_module:
        Dependency injection point that accepts a module with the same API as
        :mod:`RPi.GPIO`.  Useful for unit tests or advanced users that prefer
        :mod:`gpiozero`'s ``Device.pin_factory`` abstractions.
    auto_setup:
        Whether the GPIO pins should be configured immediately.  When set to
        ``False`` the caller needs to invoke :meth:`setup` manually before other
        operations.
    sleep_func:
        Optional callable used to delay between raising and lowering the trigger
        line. Defaults to :func:`time.sleep`.
    """

    DEFAULT_PINS = PinAssignment(power_enable=17, mode_select=27, trigger=22, status=23)

    def __init__(
        self,
        pin_assignment: Optional[Mapping[str, int]] = None,
        *,
        gpio_module=None,
        auto_setup: bool = True,
        sleep_func: Optional[Callable[[float], None]] = None,
    ) -> None:
        self._gpio = gpio_module if gpio_module is not None else _rpi_gpio
        if self._gpio is None:
            raise GPIOConfigurationError(
                "No GPIO backend available. Install RPi.GPIO or pass a compatible module."
            )

        self.pins = self._build_pins(pin_assignment)
        self._is_setup = False
        self._sleep = sleep_func if sleep_func is not None else time.sleep

        if auto_setup:
            self.setup()

    # ------------------------------------------------------------------
    # Public API
    def setup(self) -> None:
        """Configure GPIO pins according to the selected mapping."""

        if self._is_setup:
            LOGGER.debug("HW416A GPIO already configured; skipping setup call")
            return

        LOGGER.debug("Configuring GPIO pins: %s", self.pins.as_mapping())
        try:
            self._gpio.setmode(self._gpio.BCM)
            self._gpio.setup(self.pins.power_enable, self._gpio.OUT, initial=self._gpio.LOW)
            self._gpio.setup(self.pins.mode_select, self._gpio.OUT, initial=self._gpio.LOW)
            self._gpio.setup(self.pins.trigger, self._gpio.OUT, initial=self._gpio.LOW)
            self._gpio.setup(self.pins.status, self._gpio.IN, pull_up_down=self._gpio.PUD_DOWN)
        except Exception as exc:  # pragma: no cover - logged and re-raised for visibility
            LOGGER.error("Failed to configure GPIO: %s", exc)
            raise GPIOConfigurationError(str(exc)) from exc

        self._is_setup = True
        LOGGER.info("HW416A GPIO configuration completed")

    def cleanup(self) -> None:
        """Reset GPIO pins to their default state."""

        if not self._is_setup:
            LOGGER.debug("cleanup() called before setup(); nothing to reset")
            return

        LOGGER.debug("Cleaning up HW416A GPIO pins")
        self._gpio.cleanup(
            [
                self.pins.power_enable,
                self.pins.mode_select,
                self.pins.trigger,
                self.pins.status,
            ]
        )
        self._is_setup = False

    def power_on(self) -> None:
        """Enable power to the module."""

        self._ensure_ready()
        LOGGER.debug("Enabling HW416A power")
        self._gpio.output(self.pins.power_enable, self._gpio.HIGH)

    def power_off(self) -> None:
        """Disable power to the module."""

        self._ensure_ready()
        LOGGER.debug("Disabling HW416A power")
        self._gpio.output(self.pins.power_enable, self._gpio.LOW)

    def set_mode(self, *, high_speed: bool) -> None:
        """Switch between normal and high-speed mode.

        Parameters
        ----------
        high_speed:
            ``True`` selects the high-speed modulation mode, ``False`` selects
            the normal mode.
        """

        self._ensure_ready()
        level = self._gpio.HIGH if high_speed else self._gpio.LOW
        LOGGER.info("Setting HW416A mode to %s", "high-speed" if high_speed else "normal")
        self._gpio.output(self.pins.mode_select, level)

    def pulse_trigger(self, duration_s: float = 0.05) -> None:
        """Emit a short trigger pulse to toggle the sensor state."""

        if duration_s <= 0:
            raise ValueError("duration_s must be greater than zero")

        self._ensure_ready()
        LOGGER.debug("Sending trigger pulse lasting %.3f seconds", duration_s)
        self._gpio.output(self.pins.trigger, self._gpio.HIGH)
        try:
            self._sleep(duration_s)
        finally:
            self._gpio.output(self.pins.trigger, self._gpio.LOW)

    def read_status(self) -> bool:
        """Return the current logic level of the status pin."""

        self._ensure_ready()
        level = self._gpio.input(self.pins.status)
        LOGGER.debug("Read status pin level: %s", level)
        return bool(level)

    # ------------------------------------------------------------------
    # Internal helpers
    def _ensure_ready(self) -> None:
        if not self._is_setup:
            raise GPIOConfigurationError("GPIO pins are not configured; call setup() first")

    @classmethod
    def _build_pins(cls, overrides: Optional[Mapping[str, int]]) -> PinAssignment:
        base = dict(cls.DEFAULT_PINS.as_mapping())
        if overrides:
            cls._validate_overrides(overrides)
            coerced = {name: int(pin) for name, pin in overrides.items()}
            base.update(coerced)
        cls._ensure_unique_pins(base)
        return PinAssignment(**base)

    @staticmethod
    def _validate_overrides(overrides: Mapping[str, int]) -> None:
        allowed = set(PinAssignment.__annotations__.keys())
        unexpected = set(overrides) - allowed
        if unexpected:
            raise GPIOConfigurationError(f"Unknown pin names: {sorted(unexpected)}")

        try:
            {name: int(pin) for name, pin in overrides.items()}
        except Exception as exc:  # pragma: no cover - defensive guard
            raise GPIOConfigurationError("Pin numbers must be integers") from exc

    @staticmethod
    def _ensure_unique_pins(pin_mapping: Mapping[str, int]) -> None:
        seen = {}
        duplicates = set()
        for name, pin in pin_mapping.items():
            numeric_pin = int(pin)
            previous = seen.get(numeric_pin)
            if previous is not None:
                duplicates.add(numeric_pin)
            else:
                seen[numeric_pin] = name
        if duplicates:
            raise GPIOConfigurationError(
                "Pins must be unique across power, mode, trigger, and status lines; "
                f"duplicates: {sorted(duplicates)}"
            )

    # Context manager helpers -------------------------------------------------
    def __enter__(self) -> "HW416AController":
        self.setup()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()
