from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lcd1602.controller import DisplayConfigurationError, LCD1602Controller


class DummyBus:
    def __init__(self):
        self.writes = []
        self.closed = False

    def write_byte(self, address, data):
        self.writes.append((address, data))

    def close(self):
        self.closed = True


@pytest.fixture
def bus():
    return DummyBus()


def test_initialisation_sequence(bus):
    controller = LCD1602Controller(bus_factory=lambda bus_number: bus, auto_initialize=False)

    controller.initialize()

    # Initialisation sends each command twice (high and low nibble) and toggles the enable bit
    assert len(bus.writes) > 0
    first_write = bus.writes[0]
    assert first_write[0] == controller.address
    assert first_write[1] & 0xF0 in {0x30, 0x20}


def test_display_text_pads_and_sends_characters(bus):
    controller = LCD1602Controller(bus_factory=lambda bus_number: bus)
    bus.writes.clear()

    controller.display_text("Hi", line=0)

    assert any(data & 0xF0 == 0x80 for _, data in bus.writes)
    # characters H (0x48) and i (0x69) appear in high nibble writes
    high_nibbles = [data & 0xF0 for _, data in bus.writes]
    assert 0x40 in high_nibbles
    assert 0x60 in high_nibbles


def test_display_lines_updates_second_line(bus):
    controller = LCD1602Controller(bus_factory=lambda bus_number: bus)
    bus.writes.clear()

    controller.display_lines("Line1", "Line2")

    assert any(data & 0xF0 == 0xC0 for _, data in bus.writes)


def test_set_backlight_writes_state(bus):
    controller = LCD1602Controller(bus_factory=lambda bus_number: bus)
    bus.writes.clear()

    controller.set_backlight(False)
    assert bus.writes[-1] == (controller.address, 0x00)


def test_cleanup_closes_bus(bus):
    controller = LCD1602Controller(bus_factory=lambda bus_number: bus)

    controller.cleanup()
    assert bus.closed is True


def test_requires_bus_backend(monkeypatch):
    monkeypatch.setattr("lcd1602.controller._smbus_class", None)
    with pytest.raises(DisplayConfigurationError):
        LCD1602Controller(auto_initialize=False)
