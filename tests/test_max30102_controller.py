from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from max30102.controller import (  # noqa: E402
    I2CConfigurationError,
    MAX30102Controller,
    SensorCommunicationError,
)


class DummyBus:
    def __init__(self):
        self.writes = []
        self.reads = []
        self.block_reads = []
        self.registers = {}
        self.closed = False
        self.next_blocks = []
        self.fail_write = False
        self.fail_read = False

    def write_byte_data(self, address, register, value):
        if self.fail_write:
            raise OSError("write failure")
        self.writes.append((address, register, value))
        self.registers[register] = value

    def read_byte_data(self, address, register):
        if self.fail_read:
            raise OSError("read failure")
        self.reads.append((address, register))
        return self.registers.get(register, 0)

    def read_i2c_block_data(self, address, register, length):
        if self.fail_read:
            raise OSError("block failure")
        self.block_reads.append((address, register, length))
        if self.next_blocks:
            return self.next_blocks.pop(0)
        return [0] * length

    def close(self):
        self.closed = True


@pytest.fixture
def bus():
    return DummyBus()


@pytest.fixture
def controller(bus):
    return MAX30102Controller(bus=bus, sleep_func=lambda _: None)


def test_initialize_configures_expected_registers(bus):
    controller = MAX30102Controller(bus=bus, sleep_func=lambda _: None)

    assert controller.is_initialized is True
    assert bus.writes[:10] == [
        (controller.address, controller.REG_MODE_CONFIG, 0x40),
        (controller.address, controller.REG_INTR_ENABLE_1, 0x00),
        (controller.address, controller.REG_INTR_ENABLE_2, 0x00),
        (controller.address, controller.REG_FIFO_WR_PTR, 0x00),
        (controller.address, controller.REG_FIFO_OVF_COUNTER, 0x00),
        (controller.address, controller.REG_FIFO_RD_PTR, 0x00),
        (controller.address, controller.REG_FIFO_CONFIG, 0x50),
        (controller.address, controller.REG_MODE_CONFIG, controller.MODE_MAP["spo2"]),
        (controller.address, controller.REG_SPO2_CONFIG, 0x67),
        (controller.address, controller.REG_LED1_PA, 0x1F),
    ]
    # LED2 write is the 11th operation and ensures both LED currents are applied.
    assert bus.writes[10] == (controller.address, controller.REG_LED2_PA, 0x1F)


def test_shutdown_and_wake_toggle_mode_bit(controller, bus):
    bus.registers[controller.REG_MODE_CONFIG] = controller.MODE_MAP["spo2"]

    controller.shutdown()
    assert bus.registers[controller.REG_MODE_CONFIG] == controller.MODE_MAP["spo2"] | 0x80

    controller.wake()
    assert bus.registers[controller.REG_MODE_CONFIG] == controller.MODE_MAP["spo2"]


def test_set_led_current_validation(controller):
    with pytest.raises(ValueError):
        controller.set_led_current(red=-1, ir=0)
    with pytest.raises(ValueError):
        controller.set_led_current(red=0, ir=300)


def test_configure_spo2_validation(controller):
    with pytest.raises(ValueError):
        controller.configure_spo2(sample_rate=123, pulse_width=411, adc_range=16384)
    with pytest.raises(ValueError):
        controller.configure_spo2(sample_rate=100, pulse_width=999, adc_range=16384)
    with pytest.raises(ValueError):
        controller.configure_spo2(sample_rate=100, pulse_width=411, adc_range=1234)


def test_read_fifo_samples_returns_expected_values(controller, bus):
    bus.next_blocks.append(
        [
            0x00,
            0x10,
            0x20,
            0x00,
            0x30,
            0x40,
            0x00,
            0x50,
            0x60,
            0x00,
            0x70,
            0x80,
        ]
    )
    samples = controller.read_fifo_samples(count=2)
    assert samples == [(0x001020, 0x003040), (0x005060, 0x007080)]
    assert bus.block_reads == [(controller.address, controller.REG_FIFO_DATA, 12)]


def test_read_fifo_samples_requires_positive_count(controller):
    with pytest.raises(ValueError):
        controller.read_fifo_samples(count=0)


def test_read_fifo_samples_short_block_raises(controller, bus):
    bus.next_blocks.append([0x00] * 5)
    with pytest.raises(SensorCommunicationError):
        controller.read_fifo_samples(count=1)


def test_sensor_write_errors_raise_exception(controller, bus):
    bus.fail_write = True
    with pytest.raises(SensorCommunicationError):
        controller.set_led_current(red=0x10, ir=0x10)


def test_sensor_read_errors_raise_exception(controller, bus):
    bus.fail_read = True
    with pytest.raises(SensorCommunicationError):
        controller.shutdown()


def test_operations_require_initialization(bus):
    controller = MAX30102Controller(bus=bus, auto_setup=False)
    with pytest.raises(I2CConfigurationError):
        controller.shutdown()


def test_bus_factory_errors_are_wrapped():
    def failing_factory(_):
        raise RuntimeError("boom")

    with pytest.raises(I2CConfigurationError):
        MAX30102Controller(bus_factory=failing_factory, auto_setup=False)


def test_close_releases_owned_bus():
    dummy = DummyBus()
    controller = MAX30102Controller(bus_factory=lambda _: dummy, auto_setup=False)
    controller.close()
    assert dummy.closed is True
    assert controller.is_initialized is False
