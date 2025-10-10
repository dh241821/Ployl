from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ledmodule.controller import LEDConfigurationError, LEDModuleController


class DummyPWM:
    def __init__(self, pin, frequency):
        self.pin = pin
        self.frequency = frequency
        self.started = False
        self.duty_cycles = []
        self.stopped = False

    def start(self, duty_cycle):
        self.started = True
        self.duty_cycles.append(duty_cycle)

    def ChangeDutyCycle(self, duty_cycle):
        self.duty_cycles.append(duty_cycle)

    def stop(self):
        self.stopped = True


class DummyGPIO:
    BCM = "BCM"
    OUT = "OUT"

    def __init__(self):
        self.mode = None
        self.setup_calls = []
        self.cleaned_pins = []
        self.pwm_instances = []

    def setmode(self, mode):
        self.mode = mode

    def setup(self, pin, direction):
        self.setup_calls.append((pin, direction))

    def PWM(self, pin, frequency):
        pwm = DummyPWM(pin, frequency)
        self.pwm_instances.append(pwm)
        return pwm

    def cleanup(self, pin):
        self.cleaned_pins.append(pin)


@pytest.fixture
def gpio():
    return DummyGPIO()


def test_setup_creates_pwm_instance(gpio):
    controller = LEDModuleController(pin=12, frequency_hz=500, gpio_module=gpio)

    assert gpio.mode == DummyGPIO.BCM
    assert gpio.setup_calls == [(12, DummyGPIO.OUT)]
    assert len(gpio.pwm_instances) == 1
    pwm = gpio.pwm_instances[0]
    assert pwm.pin == 12
    assert pwm.frequency == 500
    assert pwm.started is True
    assert pwm.duty_cycles[0] == 0.0


def test_set_brightness_updates_duty_cycle(gpio):
    controller = LEDModuleController(gpio_module=gpio)

    controller.set_brightness(42.5)

    pwm = gpio.pwm_instances[0]
    assert pytest.approx(pwm.duty_cycles[-1]) == 42.5


def test_turn_off_and_cleanup(gpio):
    controller = LEDModuleController(gpio_module=gpio)

    controller.turn_off()
    controller.cleanup()

    pwm = gpio.pwm_instances[0]
    assert pwm.duty_cycles[-1] == 0.0
    assert pwm.stopped is True
    assert gpio.cleaned_pins == [controller.pin]


def test_blink_uses_sleep_callback(gpio):
    sleep_calls = []
    controller = LEDModuleController(gpio_module=gpio, sleep_func=lambda duration: sleep_calls.append(duration))

    controller.blink(times=2, on_time=0.1, off_time=0.2, brightness=75.0)

    pwm = gpio.pwm_instances[0]
    assert pwm.duty_cycles.count(75.0) == 2
    assert pwm.duty_cycles.count(0.0) >= 2
    assert sleep_calls == [0.1, 0.2, 0.1, 0.2]


@pytest.mark.parametrize("brightness", [-1, 101])
def test_invalid_brightness_raises(brightness, gpio):
    controller = LEDModuleController(gpio_module=gpio)
    with pytest.raises(ValueError):
        controller.set_brightness(brightness)


def test_requires_gpio_backend():
    with pytest.raises(LEDConfigurationError):
        LEDModuleController(gpio_module=None)
