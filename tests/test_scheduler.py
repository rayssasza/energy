import pytest

try:
    from src import scheduler 
except ModuleNotFoundError:
    pytest.skip("APScheduler não foi instalado, verifique.", allow_module_level=True)


def test_scheduler_jobs(monkeypatch):
    monkeypatch.setattr(scheduler, "_scheduler", None)
    sched = scheduler.start_scheduler()
    try:
        jobs = sched.get_jobs()
        assert len(jobs) == 2, "Expected two scheduled jobs"
        ids = {job.id for job in jobs}
        assert "collect_data" in ids
        assert "monthly_report" in ids
    finally:
        sched.shutdown()
