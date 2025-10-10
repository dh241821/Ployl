# Ployl HW416A helpers

This repository contains a small helper package that wraps the hardware control
logic for the HW416A module when it is connected to a Raspberry Pi.

## Installation

* Python >= 3.9 is recommended.
* Install dependencies:
  ```bash
  python -m pip install RPi.GPIO
  ```
  When running the unit tests or working on non-Raspberry Pi hardware you can
  skip installing `RPi.GPIO` and rely on the mocks that the tests provide.

Clone the repository onto your Raspberry Pi and install it in editable mode if
necessary:

```bash
python -m pip install --upgrade pip
pip install -e .
```

## Usage

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

## Development

Run the unit tests locally to ensure changes keep the configuration logic
working as expected:

```bash
python -m pytest
```
