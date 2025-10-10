"""Demonstration script for the SEN-DHT22 controller."""
import logging
import time

from sendht22 import DHT22Reading, SENDHT22Controller, SensorConfigurationError, SensorReadError

LOGGER = logging.getLogger(__name__)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )


def log_reading(reading: DHT22Reading) -> None:
    LOGGER.info(
        "Temperature: %.1f°C / %.1f°F | Humidity: %.1f%%",
        reading.temperature_c,
        reading.temperature_f,
        reading.humidity,
    )


def main() -> None:
    configure_logging()

    try:
        with SENDHT22Controller() as sensor:
            LOGGER.info("Starting SEN-DHT22 demo; press Ctrl+C to stop")
            while True:
                reading = sensor.read()
                log_reading(reading)
                time.sleep(2.0)
    except KeyboardInterrupt:
        LOGGER.info("Stopping demo")
    except SensorConfigurationError as exc:
        LOGGER.error("Sensor backend not available: %s", exc)
    except SensorReadError as exc:
        LOGGER.error("Failed to read from SEN-DHT22: %s", exc)


if __name__ == "__main__":
    main()
