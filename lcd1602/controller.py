"""I2C helper for HD44780 compatible 16x2 LCD modules with PCF8574 backpack."""
from __future__ import annotations

import logging
import time
from typing import Callable, Optional

try:  # pragma: no cover - exercised through dependency injection in tests
    from smbus2 import SMBus as _smbus_class
except ModuleNotFoundError:  # pragma: no cover - handled when no backend is available
    _smbus_class = None

LOGGER = logging.getLogger(__name__)


class DisplayConfigurationError(RuntimeError):
    """Raised when the controller cannot access the I2C bus."""


class LCD1602Controller:
    """Drive a HD44780 compatible LCD over I2C."""

    LCD_CMD = 0
    LCD_CHR = 1

    LCD_LINE_ADDRESSES = (0x80, 0xC0)

    ENABLE_BIT = 0b00000100
    BACKLIGHT_ON = 0x08

    INIT_COMMANDS = (0x33, 0x32, 0x06, 0x0C, 0x28)

    def __init__(
        self,
        bus: int = 1,
        address: int = 0x27,
        *,
        bus_factory: Optional[Callable[[int], object]] = None,
        auto_initialize: bool = True,
        sleep_func: Optional[Callable[[float], None]] = None,
    ) -> None:
        self.bus_number = int(bus)
        self.address = int(address)
        if not 0 <= self.address <= 0x7F:
            raise DisplayConfigurationError("I2C address must be between 0x00 and 0x7F")

        if bus_factory is None:
            if _smbus_class is None:
                raise DisplayConfigurationError(
                    "No SMBus backend available. Install smbus2 or provide bus_factory."
                )
            bus_factory = _smbus_class
        self._bus_factory = bus_factory

        self._sleep = sleep_func if sleep_func is not None else time.sleep
        self._backlight = self.BACKLIGHT_ON
        self._bus = None
        self._is_initialized = False

        if auto_initialize:
            self.initialize()

    # ------------------------------------------------------------------
    def initialize(self) -> None:
        """Open the I2C bus and send the LCD initialisation sequence."""

        if self._is_initialized:
            LOGGER.debug("LCD already initialised; skipping reconfiguration")
            return

        if self._bus is None:
            try:
                self._bus = self._bus_factory(self.bus_number)
            except Exception as exc:  # pragma: no cover - dependency specific errors
                LOGGER.error("Failed to open SMBus %s: %s", self.bus_number, exc)
                raise DisplayConfigurationError(str(exc)) from exc

        try:
            for command in self.INIT_COMMANDS:
                self._write_byte(command, self.LCD_CMD)
            self._is_initialized = True
            self.clear()
        except Exception as exc:  # pragma: no cover - logged and re-raised for visibility
            self._is_initialized = False
            LOGGER.error("LCD initialisation failed: %s", exc)
            raise DisplayConfigurationError(str(exc)) from exc

        LOGGER.info("LCD initialised on bus %s address 0x%02X", self.bus_number, self.address)

    def clear(self) -> None:
        """Clear the display and return the cursor to the home position."""

        self._ensure_ready()
        self._write_byte(0x01, self.LCD_CMD)
        self._sleep(0.002)  # clearing requires a slightly longer delay

    def display_text(self, text: str, line: int = 0) -> None:
        """Render text on one of the two lines of the display."""

        if line not in (0, 1):
            raise ValueError("line must be 0 or 1")

        self._ensure_ready()
        padded = text.ljust(16)[:16]
        self._write_byte(self.LCD_LINE_ADDRESSES[line], self.LCD_CMD)
        for character in padded:
            self._write_byte(ord(character), self.LCD_CHR)

    def display_lines(self, line_one: str, line_two: str) -> None:
        """Convenience helper that updates both lines."""

        self.display_text(line_one, line=0)
        self.display_text(line_two, line=1)

    def set_backlight(self, enabled: bool) -> None:
        """Switch the LCD backlight on or off."""

        self._ensure_ready()
        self._backlight = self.BACKLIGHT_ON if enabled else 0x00
        # Write a noop command to apply the change immediately
        self._bus.write_byte(self.address, self._backlight)

    def cleanup(self) -> None:
        """Close the I2C bus connection."""

        if self._bus is None:
            return

        try:
            close = getattr(self._bus, "close", None)
            if callable(close):
                close()
        finally:
            self._bus = None
            self._is_initialized = False

    # ------------------------------------------------------------------
    def __enter__(self) -> "LCD1602Controller":
        self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()

    # ------------------------------------------------------------------
    def _ensure_ready(self) -> None:
        if not self._is_initialized or self._bus is None:
            raise DisplayConfigurationError("LCD has not been initialised yet")

    def _write_byte(self, data: int, mode: int) -> None:
        self._ensure_bus()

        high_bits = mode | (data & 0xF0) | self._backlight
        low_bits = mode | ((data << 4) & 0xF0) | self._backlight

        self._bus.write_byte(self.address, high_bits)
        self._toggle_enable(high_bits)
        self._bus.write_byte(self.address, low_bits)
        self._toggle_enable(low_bits)

    def _toggle_enable(self, data: int) -> None:
        self._bus.write_byte(self.address, data | self.ENABLE_BIT)
        self._sleep(0.0005)
        self._bus.write_byte(self.address, data & ~self.ENABLE_BIT)
        self._sleep(0.0001)

    def _ensure_bus(self) -> None:
        if self._bus is None:
            raise DisplayConfigurationError("LCD bus not available; call initialize() first")
