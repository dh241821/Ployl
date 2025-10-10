import types

import pytest

from sendht22 import DHT22Reading, SENDHT22Controller, SensorConfigurationError, SensorReadError


class DummyDHTModule:
    def __init__(self, humidity=55.1, temperature=21.2):
        self.DHT22 = object()
        self._humidity = humidity
        self._temperature = temperature
        self.calls = []

    def read_retry(self, sensor, pin, *, retries, delay_seconds):
        self.calls.append(
            {
                "sensor": sensor,
                "pin": pin,
                "retries": retries,
                "delay_seconds": delay_seconds,
            }
        )
        return self._humidity, self._temperature


def test_read_returns_dataclass_with_expected_values():
    module = DummyDHTModule(humidity=43.2, temperature=19.5)
    controller = SENDHT22Controller(data_pin=17, sensor_module=module)

    reading = controller.read()

    assert isinstance(reading, DHT22Reading)
    assert reading.temperature_c == pytest.approx(19.5)
    assert reading.humidity == pytest.approx(43.2)
    assert module.calls[0]["pin"] == 17
    assert module.calls[0]["retries"] == 3
    assert module.calls[0]["delay_seconds"] == pytest.approx(2.0)


def test_temperature_f_property():
    reading = DHT22Reading(temperature_c=25.0, humidity=40.0)
    assert reading.temperature_f == pytest.approx(77.0)


def test_configuration_requires_backend_or_read_func():
    with pytest.raises(SensorConfigurationError):
        SENDHT22Controller(sensor_module=None, read_func=None)


def test_read_uses_custom_read_func():
    module = types.SimpleNamespace(DHT22="token")
    calls = []

    def custom_read(sensor, pin, *, retries, delay_seconds):
        calls.append({"sensor": sensor, "pin": pin, "retries": retries, "delay_seconds": delay_seconds})
        return 48.0, 18.0

    controller = SENDHT22Controller(sensor_module=module, read_func=custom_read, retries=1, retry_delay_s=1.5)

    reading = controller.read()

    assert reading.temperature_c == pytest.approx(18.0)
    assert reading.humidity == pytest.approx(48.0)
    assert len(calls) == 1
    call = calls[0]
    assert call["sensor"] == "token"
    assert call["pin"] == 4
    assert call["retries"] == 1
    assert call["delay_seconds"] == pytest.approx(1.5)


def test_read_failure_raises_error():
    module = DummyDHTModule()

    def returning_none(sensor, pin, *, retries, delay_seconds):
        return None, None

    controller = SENDHT22Controller(sensor_module=module, read_func=returning_none)

    with pytest.raises(SensorReadError):
        controller.read()


def test_custom_sensor_type_required_when_module_missing():
    with pytest.raises(SensorConfigurationError):
        SENDHT22Controller(sensor_module=None, read_func=lambda *args, **kwargs: (1.0, 1.0))

    controller = SENDHT22Controller(
        sensor_module=None,
        read_func=lambda *args, **kwargs: (1.0, 1.0),
        sensor_type="custom",
    )
    reading = controller.read()
    assert reading.temperature_c == pytest.approx(1.0)
    assert reading.humidity == pytest.approx(1.0)


def test_invalid_retry_configuration():
    with pytest.raises(ValueError):
        SENDHT22Controller(retries=-1)
    with pytest.raises(ValueError):
        SENDHT22Controller(retry_delay_s=0)


def test_context_manager_returns_self():
    module = DummyDHTModule()
    with SENDHT22Controller(sensor_module=module) as controller:
        assert isinstance(controller, SENDHT22Controller)
