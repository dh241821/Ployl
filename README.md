# Ployl Raspberry Pi sensor helpers

This repository collects small helper packages that encapsulate the interaction
with common Raspberry Pi peripherals:

* `hw416a` – wraps the GPIO control logic for the HW416A presence sensor.
* `max30102` – provides an I2C abstraction for the MAX30102
  pulse-oximeter/heart-rate sensor.
* `sendht22` – reads the SEN-DHT22 temperature and humidity sensor via the
  Adafruit_DHT helpers.

## Installation

* Python >= 3.9 is recommended.
* Install the hardware dependencies when running on a Raspberry Pi:
  ```bash
  python -m pip install RPi.GPIO smbus2 Adafruit_DHT
  ```
  When running the unit tests or working on non-Raspberry Pi hardware you can
  skip these optional packages and rely on the mock backends that the tests
  provide.

Clone the repository onto your Raspberry Pi and install it in editable mode if
necessary:

```bash
python -m pip install --upgrade pip
pip install -e .
```

## HW416A usage

An example script is available under `examples/hw416a_demo.py`. Run it on a
Raspberry Pi to see the basic power, mode switching and trigger functionality.

```bash
python examples/hw416a_demo.py
```

The script logs each action and prints the logic level reported by the status
pin so you can verify that your wiring matches the expected BCM pin mapping.

To use the controller in your own project:

```python
from hw416a import HW416AController

with HW416AController() as controller:
    controller.power_on()
    controller.set_mode(high_speed=True)
    controller.pulse_trigger()
    print("Status:", controller.read_status())
```

### Customising the pin mapping

If your wiring differs from the default BCM mapping (power enable = 17, mode
select = 27, trigger = 22, status = 23) you can override individual pins when
instantiating the controller. The class validates that each named signal uses a
distinct GPIO number so wiring mistakes are caught early:

```python
custom_pins = {"power_enable": 5, "status": 24}
controller = HW416AController(pin_assignment=custom_pins)
```

The controller also accepts an optional `sleep_func` parameter that defaults to
`time.sleep`. This is useful for unit tests or advanced scenarios where the
trigger pulse duration should be controlled without blocking the main thread.

## MAX30102 usage

The `max30102` package exposes a `MAX30102Controller` that hides the raw I2C
register manipulation and provides helper methods for configuring the device and
reading FIFO samples. A demonstration script can be found at
`examples/max30102_demo.py`:

```bash
python examples/max30102_demo.py
```

The script initialises the sensor, applies a sensible LED current, and prints a
few samples each second. Use it to verify that the I2C wiring and pull-ups are
working correctly.

In your own project you typically only need a handful of methods:

```python
from max30102 import MAX30102Controller

with MAX30102Controller() as sensor:
    sensor.set_led_current(red=0x24, ir=0x24)
    samples = sensor.read_fifo_samples(count=4)
    print(samples)
```

You can override configuration parameters such as sample rate, LED pulse width
and I2C address via keyword arguments when calling :meth:`initialize` or when
instantiating the controller.

## SEN-DHT22 usage

The `sendht22` package exposes a `SENDHT22Controller` that reads temperature and
humidity values from a SEN-DHT22 module. Run the demonstration script to verify
your wiring and see the logging output:

```bash
python examples/sendht22_demo.py
```

By default the controller expects the data pin to be wired to BCM pin 4. If you
use a different pin simply override the `data_pin` argument when creating the
controller. The class validates retry parameters and logs each measurement so
you can observe fluctuations in your environment:

```python
from sendht22 import SENDHT22Controller

with SENDHT22Controller(data_pin=17) as sensor:
    reading = sensor.read()
    print(reading.as_dict())
    print("Temperature in Fahrenheit:", reading.temperature_f)
```

For advanced testing scenarios you can inject a custom `read_func` compatible
with the `Adafruit_DHT.read_retry` API and even supply a custom
``sensor_type``. This allows running the unit tests on non-Raspberry Pi hosts
without accessing the real sensor hardware.

## Development

Run the unit tests locally to ensure changes keep both controllers working as
expected:

```bash
python -m pytest
```
