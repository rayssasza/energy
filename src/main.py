import argparse
import logging
import time

from src.scheduler import collect_now, start_scheduler


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logging.getLogger("pymodbus.logging").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Energy collector service")
    parser.add_argument(
        "--collect-now",
        action="store_true",
        help="Executa uma coleta imediata ao iniciar.",
    )
    parser.add_argument(
        "--collect-once",
        action="store_true",
        help="Executa uma coleta imediata e encerra o processo.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    configure_logging()

    if args.collect_once:
        collect_now()
        return

    sched = start_scheduler()
    if args.collect_now:
        collect_now()

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        sched.shutdown()


if __name__ == "__main__":
    main()
