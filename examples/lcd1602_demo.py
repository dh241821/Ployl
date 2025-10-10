"""Demonstration script for the LCD1602 controller."""
import logging
import time

from lcd1602 import DisplayConfigurationError, LCD1602Controller

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def main() -> None:
    configure_logging()

    try:
        with LCD1602Controller() as display:
            LOGGER.info("Writing welcome message to LCD")
            display.display_lines("Ployl Sensors", "Ready to log")
            time.sleep(2.0)

            LOGGER.info("Cycling through status messages")
            for countdown in range(5, 0, -1):
                display.display_lines("Sampling sensors", f"Next update: {countdown}s")
                time.sleep(1.0)

            LOGGER.info("Clearing display")
            display.clear()
            display.display_lines("Demo complete", "Goodbye!")
            time.sleep(2.0)
    except DisplayConfigurationError as exc:
        LOGGER.error("LCD controller unavailable: %s", exc)
    except KeyboardInterrupt:
        LOGGER.info("Stopping LCD demo")


if __name__ == "__main__":
    main()
