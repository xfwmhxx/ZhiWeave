from studyrag_backend.workers.celery_app import celery_app
from studyrag_backend.workers.tasks import system_ping


def test_system_ping_task_in_eager_mode() -> None:
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)

    result = system_ping.delay().get(timeout=1)

    assert result == {"status": "ok", "worker": "celery"}
