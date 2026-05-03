"""
Worker entry point.

Phase 6 will wire this up to RQ.
Phase 7 will convert it to a one-shot Fargate task runner.
For now it just starts and idles so the container stays healthy.
"""
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("BookForge worker started — awaiting Phase 6 RQ wiring")
    while True:
        time.sleep(30)


if __name__ == "__main__":
    main()
