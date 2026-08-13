from threading import Event

import pytest

from underline_retldc.core.task import TaskManager, TaskResult
from underline_retldc.plugin_api.common import TaskCancelledError


def test_task_manager_reports_success_and_failure() -> None:
    manager = TaskManager(max_workers=1)
    success = manager.submit("success", lambda context: 42)
    assert success.wait(timeout=2) == 42
    assert success.state is TaskResult.SUCCESS
    assert success.result == 42

    failure = manager.submit("failure", lambda context: 1 / 0)
    with pytest.raises(ZeroDivisionError):
        failure.wait(timeout=2)
    assert failure.state is TaskResult.FAILURE
    assert isinstance(failure.exception, ZeroDivisionError)
    manager.shutdown()


def test_task_manager_cooperative_cancellation() -> None:
    started = Event()

    def operation(context):
        started.set()
        while True:
            context.raise_if_cancelled()

    manager = TaskManager(max_workers=1)
    handle = manager.submit("cancel", operation)
    assert started.wait(timeout=2)
    handle.cancel()
    with pytest.raises(TaskCancelledError):
        handle.wait(timeout=2)
    assert handle.state is TaskResult.CANCELLED
    manager.shutdown()


def test_pending_task_cancellation_reaches_terminal_state() -> None:
    release = Event()

    def blocking_operation(context):
        release.wait(timeout=2)

    manager = TaskManager(max_workers=1)
    first = manager.submit("first", blocking_operation)
    second = manager.submit("second", lambda context: 2)
    second.cancel()
    assert second.state is TaskResult.CANCELLED
    release.set()
    first.wait(timeout=2)
    manager.shutdown()
