from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hw416a.controller import GPIOConfigurationError, HW416AController


class DummyGPIO:
    BCM = "BCM"
    OUT = "OUT"
    IN = "IN"
    LOW = 0
    HIGH = 1
    PUD_DOWN = "PUD_DOWN"

    def __init__(self):
        self.mode = None
        self.setup_calls = []
        self.output_calls = []
        self.cleanup_calls = []
        self.inputs = {}

    def setmode(self, mode):
        self.mode = mode

    def setup(self, pin, direction, **kwargs):
        self.setup_calls.append((pin, direction, kwargs))

    def output(self, pin, state):
        self.output_calls.append((pin, state))

    def input(self, pin):
        return self.inputs.get(pin, 0)

    def cleanup(self, pins=None):
        self.cleanup_calls.append(tuple(pins) if pins is not None else None)


@pytest.fixture
def gpio():
    return DummyGPIO()


def test_setup_configures_expected_pins(gpio):
    controller = HW416AController(gpio_module=gpio)

    assert controller.pins == HW416AController.DEFAULT_PINS
    assert gpio.mode == DummyGPIO.BCM
    assert gpio.setup_calls == [
        (controller.pins.power_enable, DummyGPIO.OUT, {"initial": DummyGPIO.LOW}),
        (controller.pins.mode_select, DummyGPIO.OUT, {"initial": DummyGPIO.LOW}),
        (controller.pins.trigger, DummyGPIO.OUT, {"initial": DummyGPIO.LOW}),
        (controller.pins.status, DummyGPIO.IN, {"pull_up_down": DummyGPIO.PUD_DOWN}),
    ]


def test_power_cycle_and_cleanup(gpio):
    controller = HW416AController(gpio_module=gpio)

    controller.power_on()
    controller.power_off()
    controller.cleanup()

    assert gpio.output_calls[:2] == [
        (controller.pins.power_enable, DummyGPIO.HIGH),
        (controller.pins.power_enable, DummyGPIO.LOW),
    ]
    assert gpio.cleanup_calls == [
        (
            controller.pins.power_enable,
            controller.pins.mode_select,
            controller.pins.trigger,
            controller.pins.status,
        )
    ]


def test_mode_switch_and_status_reading(gpio):
    gpio.inputs[HW416AController.DEFAULT_PINS.status] = 1
    controller = HW416AController(gpio_module=gpio)

    controller.set_mode(high_speed=True)
    controller.set_mode(high_speed=False)
    assert gpio.output_calls[-2:] == [
        (controller.pins.mode_select, DummyGPIO.HIGH),
        (controller.pins.mode_select, DummyGPIO.LOW),
    ]
    assert controller.read_status() is True


def test_pulse_trigger(gpio):
    sleep_calls = []
    controller = HW416AController(gpio_module=gpio, sleep_func=lambda duration: sleep_calls.append(duration))

    controller.pulse_trigger(duration_s=0.01)
    assert gpio.output_calls[-2:] == [
        (controller.pins.trigger, DummyGPIO.HIGH),
        (controller.pins.trigger, DummyGPIO.LOW),
    ]
    assert sleep_calls == [0.01]


@pytest.mark.parametrize("overrides", [{"power_enable": 5}, {"mode_select": 5, "trigger": 6}])
def test_pin_override_merging(overrides, gpio):
    controller = HW416AController(pin_assignment=overrides, gpio_module=gpio)
    for key, value in overrides.items():
        assert getattr(controller.pins, key) == value


@pytest.mark.parametrize(
    "overrides",
    [
        {"unknown": 3},
        {"power_enable": "A"},
        {"power_enable": 4, "trigger": 4},
    ],
)
def test_pin_override_validation_errors(overrides, gpio):
    with pytest.raises(GPIOConfigurationError):
        HW416AController(pin_assignment=overrides, gpio_module=gpio)


def test_pin_override_cannot_duplicate_default_pin(gpio):
    duplicate_pin = HW416AController.DEFAULT_PINS.power_enable
    with pytest.raises(GPIOConfigurationError):
        HW416AController(pin_assignment={"mode_select": duplicate_pin}, gpio_module=gpio)


def test_requires_gpio_backend():
    with pytest.raises(GPIOConfigurationError):
        HW416AController(gpio_module=None)


def test_manual_setup_allows_delayed_configuration(gpio):
    controller = HW416AController(gpio_module=gpio, auto_setup=False)
    assert gpio.setup_calls == []
    controller.setup()
    controller.setup()  # second call is ignored
    assert len(gpio.setup_calls) == 4

    controller.cleanup()
    controller.cleanup()  # no additional cleanup when already done
    assert len(gpio.cleanup_calls) == 1


def test_context_manager_triggers_setup_and_cleanup(gpio):
    with HW416AController(gpio_module=gpio, auto_setup=False) as controller:
        assert controller.pins == HW416AController.DEFAULT_PINS
        controller.power_on()
    assert gpio.cleanup_calls


def test_pulse_trigger_rejects_non_positive_duration(gpio):
    controller = HW416AController(gpio_module=gpio)
    with pytest.raises(ValueError):
        controller.pulse_trigger(duration_s=0)
