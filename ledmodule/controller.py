"""High-level PWM LED module controller for Raspberry Pi GPIO pins."""
from __future__ import annotations

import logging
import time
from typing import Callable, Optional

try:  # pragma: no cover - optional dependency resolved via injection in tests
    import RPi.GPIO as _rpi_gpio
except ModuleNotFoundError:  # pragma: no cover - handled at runtime when no backend provided
    _rpi_gpio = None

LOGGER = logging.getLogger(__name__)


class LEDConfigurationError(RuntimeError):
    """Raised when the LED controller cannot access the GPIO subsystem."""


class LEDModuleController:
    """Convenience wrapper around a PWM-driven LED channel.

    Parameters
    ----------
    pin:
        BCM pin number connected to the LED anode via a suitable resistor.
        Defaults to GPIO18 which supports hardware PWM on Raspberry Pi boards.
    gpio_module:
        Optional GPIO backend. Falls back to :mod:`RPi.GPIO` when available.
    frequency_hz:
        PWM frequency used for brightness control.
    auto_setup:
        Whether to configure the GPIO pin during initialisation.
    sleep_func:
        Optional delay function used by :meth:`blink`. Defaults to
        :func:`time.sleep`.
    """

    DEFAULT_PIN = 18

    def __init__(
        self,
        pin: int = DEFAULT_PIN,
        *,
        gpio_module=None,
        frequency_hz: int = 1000,
        auto_setup: bool = True,
        sleep_func: Optional[Callable[[float], None]] = None,
    ) -> None:
        self._gpio = gpio_module if gpio_module is not None else _rpi_gpio
        if self._gpio is None:
            raise LEDConfigurationError(
                "No GPIO backend available. Install RPi.GPIO or provide a compatible module."
            )

        try:
            self.pin = int(pin)
        except Exception as exc:  # pragma: no cover - defensive branch
            raise LEDConfigurationError("pin must be coercible to an integer") from exc
        if self.pin < 0:
            raise LEDConfigurationError("pin must be a non-negative integer")

        try:
            self.frequency_hz = int(frequency_hz)
        except Exception as exc:  # pragma: no cover - defensive branch
            raise LEDConfigurationError("frequency_hz must be coercible to an integer") from exc
        if self.frequency_hz <= 0:
            raise LEDConfigurationError("frequency_hz must be greater than zero")

        self._sleep = sleep_func if sleep_func is not None else time.sleep
        self._pwm = None
        self._is_setup = False

        if auto_setup:
            self.setup()

    # ------------------------------------------------------------------
    def setup(self) -> None:
        """Configure the GPIO pin for PWM output."""

        if self._is_setup:
            LOGGER.debug("LED GPIO already configured; skipping setup")
            return

        try:
            self._gpio.setmode(self._gpio.BCM)
            self._gpio.setup(self.pin, self._gpio.OUT)
            pwm = self._gpio.PWM(self.pin, self.frequency_hz)
            pwm.start(0.0)
        except Exception as exc:  # pragma: no cover - logged for observability
            LOGGER.error("Failed to configure LED GPIO: %s", exc)
            raise LEDConfigurationError(str(exc)) from exc

        self._pwm = pwm
        self._is_setup = True
        LOGGER.info("LED PWM configured on BCM pin %s at %s Hz", self.pin, self.frequency_hz)

    def cleanup(self) -> None:
        """Reset the GPIO pin and stop PWM output."""

        if not self._is_setup:
            LOGGER.debug("cleanup() called before setup(); nothing to do")
            return

        if self._pwm is not None:
            self._pwm.stop()
            self._pwm = None

        self._gpio.cleanup(self.pin)
        self._is_setup = False
        LOGGER.info("LED PWM on BCM pin %s stopped", self.pin)

    # ------------------------------------------------------------------
    def set_brightness(self, duty_cycle: float) -> None:
        """Adjust LED brightness using a duty cycle between 0 and 100."""

        if not 0.0 <= duty_cycle <= 100.0:
            raise ValueError("duty_cycle must be between 0 and 100")

        pwm = self._ensure_ready()
        LOGGER.debug("Setting LED duty cycle to %.1f%%", duty_cycle)
        pwm.ChangeDutyCycle(float(duty_cycle))

    def turn_on(self, *, brightness: float = 100.0) -> None:
        """Switch the LED on using the specified brightness percentage."""

        self.set_brightness(brightness)

    def turn_off(self) -> None:
        """Switch the LED completely off."""

        self.set_brightness(0.0)

    def blink(
        self,
        *,
        times: int = 3,
        on_time: float = 0.2,
        off_time: float = 0.2,
        brightness: float = 100.0,
    ) -> None:
        """Blink the LED a number of times using the configured duty cycle."""

        if times < 0:
            raise ValueError("times must be non-negative")
        if on_time < 0 or off_time < 0:
            raise ValueError("on_time and off_time must be non-negative")

        pwm = self._ensure_ready()
        LOGGER.info(
            "Blinking LED %s times (on %.3fs/off %.3fs) at %.1f%% brightness",
            times,
            on_time,
            off_time,
            brightness,
        )
        for _ in range(times):
            pwm.ChangeDutyCycle(float(brightness))
            self._sleep(on_time)
            pwm.ChangeDutyCycle(0.0)
            self._sleep(off_time)

    # ------------------------------------------------------------------
    def __enter__(self) -> "LEDModuleController":
        self.setup()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.cleanup()

    # ------------------------------------------------------------------
    def _ensure_ready(self):
        if not self._is_setup or self._pwm is None:
            raise LEDConfigurationError("LED GPIO not initialised; call setup() first")
        return self._pwm
