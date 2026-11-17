import subprocess
from collections.abc import Callable

TRASH_BIN = "/usr/bin/trash"


class TrashError(Exception):
    pass


def move_to_trash(path: str, runner: Callable[[list[str]], int] | None = None) -> None:
    if not path.startswith("/"):
        raise TrashError("trash failed")
    argv = [TRASH_BIN, "-s", path]
    if "--" in argv:
        raise TrashError("trash failed")
    run = _run if runner is None else runner
    try:
        code = run(argv)
    except FileNotFoundError as exc:
        raise TrashError("trash not found") from exc
    if code != 0:
        raise TrashError("trash failed")


def _run(argv: list[str]) -> int:
    completed = subprocess.run(argv, check=False, capture_output=True)
    return completed.returncode
