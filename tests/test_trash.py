import pytest

from dustsweeper.trash import TrashError, move_to_trash


def test_trash_argv_has_no_double_dash():
    seen: list[list[str]] = []

    def runner(argv: list[str]) -> int:
        seen.append(argv)
        return 0

    move_to_trash("/tmp/item", runner)
    assert seen == [["/usr/bin/trash", "-s", "/tmp/item"]]
    assert "--" not in seen[0]


def test_relative_path_does_not_call_runner():
    def runner(argv: list[str]) -> int:
        raise AssertionError(argv)

    with pytest.raises(TrashError, match="trash failed"):
        move_to_trash("tmp/item", runner)


def test_missing_trash_binary():
    def runner(argv: list[str]) -> int:
        raise FileNotFoundError(argv[0])

    with pytest.raises(TrashError, match="trash not found"):
        move_to_trash("/tmp/item", runner)


def test_nonzero_exit_keeps_message():
    with pytest.raises(TrashError, match="trash failed"):
        move_to_trash("/tmp/item", lambda argv: 1)
