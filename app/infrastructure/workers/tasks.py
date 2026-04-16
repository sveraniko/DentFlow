from collections.abc import Awaitable, Callable

WorkerTask = Callable[[], Awaitable[None]]


class TaskRegistry:
    def __init__(self) -> None:
        self._tasks: dict[str, WorkerTask] = {}

    def register(self, name: str, task: WorkerTask) -> None:
        self._tasks[name] = task

    def items(self) -> list[tuple[str, WorkerTask]]:
        return list(self._tasks.items())


async def placeholder_heartbeat_task() -> None:
    return None
