"""MAX30102 controller abstraction for Raspberry Pi projects."""
from __future__ import annotations

import logging
import time
from typing import Callable, Iterable, List, Optional, Sequence, Tuple

try:  # pragma: no cover - optional dependency handled by dependency injection
    from smbus2 import SMBus  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - handled at runtime
    SMBus = None  # type: ignore[assignment]

LOGGER = logging.getLogger(__name__)


class I2CConfigurationError(RuntimeError):
    """Raised when the controller cannot access the I2C bus."""


class SensorCommunicationError(RuntimeError):
    """Raised when communication with the sensor fails."""


class MAX30102Controller:
    """High level wrapper around the MAX30102 pulse oximeter/heart-rate sensor.

    Parameters
    ----------
    bus:
        Optional, pre-configured I2C bus instance exposing the subset of the
        :class:`smbus2.SMBus` API used by the controller. When omitted the class
        attempts to instantiate :class:`smbus2.SMBus` with ``bus_number``.
    bus_factory:
        Optional callable that receives ``bus_number`` and returns an I2C bus
        instance. This is primarily useful for unit tests where the smbus2
        dependency is not available.
    bus_number:
        I2C bus number used when a new bus instance is created. On Raspberry Pi
        devices this defaults to ``1`` which maps to ``/dev/i2c-1``.
    address:
        I2C address of the MAX30102 sensor. The default ``0x57`` matches most
        breakout boards.
    auto_setup:
        Whether the controller should immediately initialise the sensor using
        :meth:`initialize`.
    sleep_func:
        Optional callable used to delay between register writes. Defaults to
        :func:`time.sleep`.
    reset_delay:
        Number of seconds to sleep after issuing a soft reset. The default is
        sufficient for typical hardware but can be overridden for unit tests or
        unusual environments.
    """

    REG_INTR_STATUS_1 = 0x00
    REG_INTR_STATUS_2 = 0x01
    REG_INTR_ENABLE_1 = 0x02
    REG_INTR_ENABLE_2 = 0x03
    REG_FIFO_WR_PTR = 0x04
    REG_FIFO_OVF_COUNTER = 0x05
    REG_FIFO_RD_PTR = 0x06
    REG_FIFO_DATA = 0x07
    REG_FIFO_CONFIG = 0x08
    REG_MODE_CONFIG = 0x09
    REG_SPO2_CONFIG = 0x0A
    REG_LED1_PA = 0x0C
    REG_LED2_PA = 0x0D
    REG_MULTI_LED_CTRL1 = 0x11
    REG_MULTI_LED_CTRL2 = 0x12

    SAMPLE_AVERAGE_MAP = {1: 0b000, 2: 0b001, 4: 0b010, 8: 0b011, 16: 0b100, 32: 0b101}
    SAMPLE_RATE_MAP = {50: 0b000, 100: 0b001, 200: 0b010, 400: 0b011, 800: 0b100, 1000: 0b101, 1600: 0b110, 3200: 0b111}
    PULSE_WIDTH_MAP = {69: 0b00, 118: 0b01, 215: 0b10, 411: 0b11}
    ADC_RANGE_MAP = {2048: 0b00, 4096: 0b01, 8192: 0b10, 16384: 0b11}
    MODE_MAP = {"heart_rate": 0x02, "spo2": 0x03, "multi_led": 0x07}

    DEFAULT_ADDRESS = 0x57

    def __init__(
        self,
        *,
        bus=None,
        bus_factory: Optional[Callable[[int], object]] = None,
        bus_number: int = 1,
        address: int = DEFAULT_ADDRESS,
        auto_setup: bool = True,
        sleep_func: Optional[Callable[[float], None]] = None,
        reset_delay: float = 0.05,
    ) -> None:
        if bus is not None and bus_factory is not None:
            raise ValueError("Provide either bus or bus_factory, not both")

        self.address = int(address)
        self._sleep = sleep_func if sleep_func is not None else time.sleep
        self._reset_delay = reset_delay
        self._bus = self._initialise_bus(bus, bus_factory, bus_number)
        self._owns_bus = bus is None
        self._initialized = False

        if auto_setup:
            self.initialize()

    # ------------------------------------------------------------------
    # Lifecycle helpers
    def initialize(
        self,
        *,
        sample_average: int = 4,
        sample_rate: int = 100,
        pulse_width: int = 411,
        adc_range: int = 16384,
        mode: str = "spo2",
        red_led_current: int = 0x1F,
        ir_led_current: int = 0x1F,
        fifo_rollover: bool = True,
        fifo_a_full: int = 0,
    ) -> None:
        """Reset and configure the sensor using typical defaults."""

        if self._initialized:
            LOGGER.debug("MAX30102 already initialised; skipping reconfiguration")
            return

        LOGGER.info("Initialising MAX30102 sensor at address 0x%02X", self.address)
        self.reset()
        self._write_register(self.REG_INTR_ENABLE_1, 0x00)
        self._write_register(self.REG_INTR_ENABLE_2, 0x00)
        self.clear_fifo()
        self.configure_fifo(sample_average=sample_average, fifo_rollover=fifo_rollover, fifo_a_full=fifo_a_full)
        self.set_mode(mode)
        self.configure_spo2(sample_rate=sample_rate, pulse_width=pulse_width, adc_range=adc_range)
        self.set_led_current(red_led_current, ir_led_current)
        if mode == "multi_led":
            # Enable slots for red and IR LEDs in multi-led mode.
            self._write_register(self.REG_MULTI_LED_CTRL1, 0x21)
            self._write_register(self.REG_MULTI_LED_CTRL2, 0x03)
        self._initialized = True
        LOGGER.info("MAX30102 initialisation completed")

    def close(self) -> None:
        """Release the I2C bus if it is owned by the controller."""

        if self._bus is not None and self._owns_bus:
            try:
                close = getattr(self._bus, "close", None)
                if callable(close):
                    close()
            finally:
                self._bus = None
                self._initialized = False

    # ------------------------------------------------------------------
    def reset(self) -> None:
        """Issue a soft reset to the sensor."""

        self._write_register(self.REG_MODE_CONFIG, 0x40)
        self._sleep(self._reset_delay)

    def clear_fifo(self) -> None:
        """Reset FIFO pointers to empty the sample buffer."""

        self._write_register(self.REG_FIFO_WR_PTR, 0x00)
        self._write_register(self.REG_FIFO_OVF_COUNTER, 0x00)
        self._write_register(self.REG_FIFO_RD_PTR, 0x00)

    def configure_fifo(self, *, sample_average: int, fifo_rollover: bool, fifo_a_full: int) -> None:
        self._ensure_supported("sample_average", sample_average, self.SAMPLE_AVERAGE_MAP.keys())
        if not 0 <= fifo_a_full <= 0x0F:
            raise ValueError("fifo_a_full must be between 0 and 15")

        config = self.SAMPLE_AVERAGE_MAP[sample_average] << 5
        if fifo_rollover:
            config |= 0x10
        config |= fifo_a_full & 0x0F
        self._write_register(self.REG_FIFO_CONFIG, config)

    def configure_spo2(self, *, sample_rate: int, pulse_width: int, adc_range: int) -> None:
        self._ensure_supported("sample_rate", sample_rate, self.SAMPLE_RATE_MAP.keys())
        self._ensure_supported("pulse_width", pulse_width, self.PULSE_WIDTH_MAP.keys())
        self._ensure_supported("adc_range", adc_range, self.ADC_RANGE_MAP.keys())

        value = (
            (self.ADC_RANGE_MAP[adc_range] << 5)
            | (self.SAMPLE_RATE_MAP[sample_rate] << 2)
            | self.PULSE_WIDTH_MAP[pulse_width]
        )
        self._write_register(self.REG_SPO2_CONFIG, value)

    def set_mode(self, mode: str) -> None:
        self._ensure_supported("mode", mode, self.MODE_MAP.keys())
        self._write_register(self.REG_MODE_CONFIG, self.MODE_MAP[mode])

    def set_led_current(self, red: int, ir: int) -> None:
        for label, value in {"red": red, "ir": ir}.items():
            if not 0 <= int(value) <= 255:
                raise ValueError(f"{label} LED current must be within 0-255")
        self._write_register(self.REG_LED1_PA, int(red) & 0xFF)
        self._write_register(self.REG_LED2_PA, int(ir) & 0xFF)

    def shutdown(self) -> None:
        """Put the sensor into low-power shutdown mode."""

        self._ensure_ready()
        self._modify_register(self.REG_MODE_CONFIG, lambda value: value | 0x80)

    def wake(self) -> None:
        """Bring the sensor out of shutdown mode."""

        self._ensure_ready()
        self._modify_register(self.REG_MODE_CONFIG, lambda value: value & ~0x80)
        self._sleep(self._reset_delay)

    def read_fifo_samples(self, count: int = 1) -> List[Tuple[int, int]]:
        """Read ``count`` samples from the FIFO buffer.

        Each returned tuple contains the raw red and IR readings.
        """

        if count <= 0:
            raise ValueError("count must be a positive integer")
        self._ensure_ready()

        bytes_to_read = count * 6
        data = self._read_block(self.REG_FIFO_DATA, bytes_to_read)
        if len(data) != bytes_to_read:
            raise SensorCommunicationError(
                f"Expected {bytes_to_read} bytes from FIFO but received {len(data)}"
            )

        samples: List[Tuple[int, int]] = []
        for offset in range(0, bytes_to_read, 6):
            red = ((data[offset] << 16) | (data[offset + 1] << 8) | data[offset + 2]) & 0x3FFFF
            ir = ((data[offset + 3] << 16) | (data[offset + 4] << 8) | data[offset + 5]) & 0x3FFFF
            samples.append((red, ir))
        return samples

    # ------------------------------------------------------------------
    def _initialise_bus(
        self,
        bus,
        bus_factory: Optional[Callable[[int], object]],
        bus_number: int,
    ):
        if bus is not None:
            return bus

        if bus_factory is not None:
            try:
                created_bus = bus_factory(bus_number)
            except Exception as exc:  # pragma: no cover - defensive logging path
                raise I2CConfigurationError(f"Failed to create I2C bus via factory: {exc}") from exc
            if created_bus is None:
                raise I2CConfigurationError("Bus factory returned None")
            return created_bus

        if SMBus is None:
            raise I2CConfigurationError("smbus2 is not available; install it or pass a bus instance")

        try:
            return SMBus(bus_number)
        except Exception as exc:  # pragma: no cover - depends on host configuration
            raise I2CConfigurationError(f"Failed to open I2C bus {bus_number}: {exc}") from exc

    def _ensure_supported(self, name: str, value, supported: Iterable) -> None:
        if value not in supported:
            raise ValueError(f"Unsupported {name}: {value}. Supported values: {sorted(supported)}")

    def _ensure_ready(self) -> None:
        if not self._initialized:
            raise I2CConfigurationError("Sensor not initialised; call initialize() first")

    def _write_register(self, register: int, value: int) -> None:
        self._ensure_bus()
        try:
            self._bus.write_byte_data(self.address, register & 0xFF, value & 0xFF)  # type: ignore[operator]
        except OSError as exc:
            raise SensorCommunicationError(f"Failed to write register 0x{register:02X}: {exc}") from exc

    def _read_register(self, register: int) -> int:
        self._ensure_bus()
        try:
            return int(self._bus.read_byte_data(self.address, register & 0xFF))  # type: ignore[operator]
        except OSError as exc:
            raise SensorCommunicationError(f"Failed to read register 0x{register:02X}: {exc}") from exc

    def _modify_register(self, register: int, transform: Callable[[int], int]) -> int:
        current = self._read_register(register)
        updated = transform(current) & 0xFF
        self._write_register(register, updated)
        return updated

    def _read_block(self, register: int, length: int) -> Sequence[int]:
        self._ensure_bus()
        try:
            result = self._bus.read_i2c_block_data(self.address, register & 0xFF, length)  # type: ignore[operator]
        except OSError as exc:
            raise SensorCommunicationError(f"Failed to read block from 0x{register:02X}: {exc}") from exc
        return result

    def _ensure_bus(self) -> None:
        if self._bus is None:
            raise I2CConfigurationError("I2C bus is not available")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    # Context manager helpers -------------------------------------------------
    def __enter__(self) -> "MAX30102Controller":
        if not self._initialized:
            self.initialize()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
