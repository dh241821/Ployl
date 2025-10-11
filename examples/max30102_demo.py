"""Demonstration script for the MAX30102 controller."""
import logging
import time

from max30102 import I2CConfigurationError, MAX30102Controller, SensorCommunicationError

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def main() -> None:
    configure_logging()

    try:
        with MAX30102Controller() as sensor:
            LOGGER.info("Sensor initialised; adjusting LED current and starting capture")
            sensor.set_led_current(red=0x24, ir=0x24)

            LOGGER.info("Reading FIFO samples. Press Ctrl+C to stop.")
            while True:
                samples = sensor.read_fifo_samples(count=4)
                for index, (red, ir) in enumerate(samples, start=1):
                    LOGGER.info("Sample %d: RED=%d IR=%d", index, red, ir)
                time.sleep(1.0)
    except KeyboardInterrupt:
        LOGGER.info("Stopping demo")
    except I2CConfigurationError as exc:
        LOGGER.error("Unable to access the I2C bus: %s", exc)
    except SensorCommunicationError as exc:
        LOGGER.error("Communication with the MAX30102 failed: %s", exc)


if __name__ == "__main__":
    main()
