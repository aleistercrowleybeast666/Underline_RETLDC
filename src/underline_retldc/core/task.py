from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from enum import StrEnum
from threading import Event, Lock
from typing import Any, Generic, TypeVar

from underline_retldc.plugin_api.common import TaskCancelledError, TaskContext

T = TypeVar("T")


class TaskResult(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"


class TaskHandle(Generic[T]):
    def __init__(self, name: str) -> None:
        self.name = name
        self._state = TaskResult.PENDING
        self._progress = 0.0
        self._message = ""
        self._result: T | None = None
        self._exception: BaseException | None = None
        self._cancellation_event = Event()
        self._future: Future[T] | None = None
        self._lock = Lock()

    @property
    def state(self) -> TaskResult:
        with self._lock:
            return self._state

    @property
    def progress(self) -> float:
        with self._lock:
            return self._progress

    @property
    def message(self) -> str:
        with self._lock:
            return self._message

    @property
    def result(self) -> T | None:
        with self._lock:
            return self._result

    @property
    def exception(self) -> BaseException | None:
        with self._lock:
            return self._exception

    @property
    def done(self) -> bool:
        return self.state in {TaskResult.SUCCESS, TaskResult.FAILURE, TaskResult.CANCELLED}

    def wait(self, timeout: float | None = None) -> T:
        if self._future is None:
            raise RuntimeError("Task has not been submitted")
        return self._future.result(timeout=timeout)

    def cancel(self) -> None:
        self._cancellation_event.set()
        if self._future is not None and self._future.cancel():
            self._state_update(
                TaskResult.CANCELLED,
                exception=TaskCancelledError("Task was cancelled before it started"),
            )

    def _progress_update(self, progress: float, message: str) -> None:
        with self._lock:
            self._progress = progress
            self._message = message

    def _state_update(
        self,
        state: TaskResult,
        *,
        result: T | None = None,
        exception: BaseException | None = None,
    ) -> None:
        with self._lock:
            self._state = state
            self._result = result
            self._exception = exception
            if state is TaskResult.SUCCESS:
                self._progress = 1.0


class TaskManager:
    def __init__(self, *, max_workers: int = 2) -> None:
        if max_workers < 1:
            raise ValueError("max_workers must be positive")
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="retldc")
        self._handles: list[TaskHandle[Any]] = []

    def submit(self, name: str, operation: Callable[[TaskContext], T]) -> TaskHandle[T]:
        handle: TaskHandle[T] = TaskHandle(name)

        def run() -> T:
            handle._state_update(TaskResult.RUNNING)
            context = TaskContext(
                cancellation_event=handle._cancellation_event,
                progress_callback=handle._progress_update,
            )
            try:
                value = operation(context)
                context.raise_if_cancelled()
            except TaskCancelledError as exc:
                handle._state_update(TaskResult.CANCELLED, exception=exc)
                raise
            except BaseException as exc:
                handle._state_update(TaskResult.FAILURE, exception=exc)
                raise
            handle._state_update(TaskResult.SUCCESS, result=value)
            return value

        handle._future = self._executor.submit(run)
        self._handles.append(handle)
        return handle

    @property
    def tasks(self) -> tuple[TaskHandle[Any], ...]:
        return tuple(self._handles)

    def shutdown(self, *, wait: bool = True, cancel_pending: bool = False) -> None:
        if cancel_pending:
            for handle in self._handles:
                if not handle.done:
                    handle.cancel()
        self._executor.shutdown(wait=wait, cancel_futures=cancel_pending)
