from __future__ import annotations

import datetime as dt
import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from src import config
from src import data_processing
from src import modbus_client
from src import report

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def _collect_data() -> None:
    now = dt.datetime.now(dt.timezone(dt.timedelta(hours=-3)))
    success_count = 0
    failure_count = 0

    for company_key in config.COMPANIES:
        try:
            raw_values = modbus_client.read_company(company_key)
            cumulative, delta = data_processing.store_reading(company_key, raw_values, timestamp=now)
            logger.info("Empresa %s reading: cumulative=%s, delta_kwh=%s", company_key, cumulative, delta)
            success_count += 1
        except Exception as exc:
            logger.warning("Error reading Empresa %s: %s", company_key, exc)
            failure_count += 1

    if failure_count > 0:
        logger.warning("Collection finished with failures: success=%s failure=%s", success_count, failure_count)


def collect_now() -> None:
    _collect_data()


def _generate_monthly_report() -> None:
    try:
        report.generate_and_send_report()
        logger.info("Monthly report generated and sent.")
    except Exception as exc:
        logger.exception("Error generating monthly report: %s", exc)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        _collect_data,
        IntervalTrigger(minutes=15),
        id="collect_data",
        coalesce=True,
        next_run_time=dt.datetime.now(dt.timezone(dt.timedelta(hours=-3))),
    )
    scheduler.add_job(
        _generate_monthly_report,
        CronTrigger(day=config.REPORT_DAY, hour=8, minute=0),
        id="monthly_report",
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("Scheduler started with jobs: %s", scheduler.get_jobs())
    return scheduler
