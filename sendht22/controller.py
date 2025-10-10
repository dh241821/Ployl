"""High level wrapper around the SEN-DHT22 temperature/humidity sensor."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable, Optional

try:  # pragma: no cover - optional dependency resolved in __init__
    import Adafruit_DHT as _adafruit_dht
except ModuleNotFoundError:  # pragma: no cover - handled via configuration error
    _adafruit_dht = None

LOGGER = logging.getLogger(__name__)


class SensorConfigurationError(RuntimeError):
    """Raised when the SEN-DHT22 controller cannot access the backend library."""


class SensorReadError(RuntimeError):
    """Raised when the sensor fails to provide a valid measurement."""


@dataclass(frozen=True)
class DHT22Reading:
    """Container for a single SEN-DHT22 measurement."""

    temperature_c: float
    humidity: float

    @property
    def temperature_f(self) -> float:
        """Return the temperature converted to degrees Fahrenheit."""

        return (self.temperature_c * 9.0 / 5.0) + 32.0

    def as_dict(self) -> dict[str, float]:
        """Return the reading as a mapping for convenience."""

        return {"temperature_c": self.temperature_c, "humidity": self.humidity}


class SENDHT22Controller:
    """Encapsulates the Adafruit_DHT access required for a SEN-DHT22 sensor."""

    DEFAULT_DATA_PIN = 4

    def __init__(
        self,
        data_pin: int = DEFAULT_DATA_PIN,
        *,
        sensor_module=None,
        read_func: Optional[Callable[..., tuple[Optional[float], Optional[float]]]] = None,
        sensor_type=None,
        retries: int = 3,
        retry_delay_s: float = 2.0,
    ) -> None:
        self.data_pin = int(data_pin)
        if retries < 0:
            raise ValueError("retries must be zero or a positive integer")
        if retry_delay_s <= 0:
            raise ValueError("retry_delay_s must be greater than zero")
        self.retries = int(retries)
        self.retry_delay_s = float(retry_delay_s)

        self._module = sensor_module if sensor_module is not None else _adafruit_dht
        self._read_func = read_func

        if self._module is None and self._read_func is None:
            raise SensorConfigurationError(
                "No Adafruit_DHT backend available. Install Adafruit_DHT or provide read_func."
            )

        if self._read_func is None:
            try:
                self._read_func = self._module.read_retry
            except AttributeError as exc:  # pragma: no cover - defensive guard
                raise SensorConfigurationError("sensor_module lacks read_retry function") from exc

        if sensor_type is not None:
            self._sensor_type = sensor_type
        else:
            if self._module is None:
                raise SensorConfigurationError("sensor_type must be provided when no module is available")
            try:
                self._sensor_type = self._module.DHT22
            except AttributeError as exc:  # pragma: no cover - defensive guard
                raise SensorConfigurationError("sensor_module lacks DHT22 constant") from exc

    # ------------------------------------------------------------------
    # Public API
    def read(self) -> DHT22Reading:
        """Read a single measurement from the sensor."""

        humidity, temperature = self._perform_read()
        if humidity is None or temperature is None:
            raise SensorReadError("Failed to read humidity/temperature from SEN-DHT22")

        reading = DHT22Reading(temperature_c=float(temperature), humidity=float(humidity))
        LOGGER.debug(
            "DHT22 measurement: temperature_c=%.2f humidity=%.2f", reading.temperature_c, reading.humidity
        )
        return reading

    def read_fahrenheit(self) -> DHT22Reading:
        """Read a measurement and expose the Fahrenheit helper via the dataclass."""

        return self.read()

    # Context manager helpers -------------------------------------------------
    def __enter__(self) -> "SENDHT22Controller":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # Nothing to clean up; method provided for parity with other controllers.
        return None

    # Internal helpers --------------------------------------------------------
    def _perform_read(self) -> tuple[Optional[float], Optional[float]]:
        LOGGER.debug(
            "Reading SEN-DHT22 via data_pin=%s retries=%d retry_delay_s=%.2f", self.data_pin, self.retries, self.retry_delay_s
        )
        return self._read_func(
            self._sensor_type,
            self.data_pin,
            retries=self.retries,
            delay_seconds=self.retry_delay_s,
        )
