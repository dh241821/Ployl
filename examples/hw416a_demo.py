"""Demonstration script for driving the HW416A module on a Raspberry Pi."""
from __future__ import annotations

import logging
import time

from hw416a import HW416AController, GPIOConfigurationError


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
LOGGER = logging.getLogger("hw416a.demo")


def demo_sequence() -> None:
    """Run a simple demonstration sequence showing typical controller usage."""

    LOGGER.info("Starting HW416A demonstration sequence")
    try:
        with HW416AController() as controller:
            LOGGER.info("Powering on the module")
            controller.power_on()
            time.sleep(0.5)

            LOGGER.info("Switching to high-speed mode")
            controller.set_mode(high_speed=True)
            time.sleep(0.5)

            for idx in range(3):
                LOGGER.info("Issuing trigger pulse %s", idx + 1)
                controller.pulse_trigger(duration_s=0.1)
                LOGGER.info("Status pin level: %s", controller.read_status())
                time.sleep(0.3)

            LOGGER.info("Reverting to normal mode and powering down")
            controller.set_mode(high_speed=False)
            controller.power_off()
    except GPIOConfigurationError as exc:
        LOGGER.error("Failed to run demo: %s", exc)
    finally:
        LOGGER.info("HW416A demonstration finished")


if __name__ == "__main__":
    demo_sequence()
