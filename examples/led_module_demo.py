"""Demonstration script for the PWM LED module controller."""
import logging
import time

from ledmodule import LEDConfigurationError, LEDModuleController

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    configure_logging()

    try:
        with LEDModuleController() as led:
            LOGGER.info("Blinking LED to signal startup")
            led.blink(times=3, on_time=0.2, off_time=0.2, brightness=80)

            LOGGER.info("Holding LED at half brightness for 2 seconds")
            led.turn_on(brightness=50)
            time.sleep(2.0)

            LOGGER.info("Turning LED off")
            led.turn_off()
    except LEDConfigurationError as exc:
        LOGGER.error("LED controller unavailable: %s", exc)
    except KeyboardInterrupt:
        LOGGER.info("Stopping LED demo")


if __name__ == "__main__":
    main()
