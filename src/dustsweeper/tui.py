import curses
import os
import subprocess
import sys
import threading
from pathlib import Path

from dustsweeper.model import ScanError
from dustsweeper.trash import TrashError, move_to_trash
from dustsweeper.tree import (
    BrowseState,
    Row,
    TreeNode,
    apply_key,
    clamp_selected,
    drop_child,
    dust_browse_argv,
    initial_state,
    parse_tree,
    render_header,
    render_path,
    render_row,
    size_column_width,
    status_line,
    visible_rows,
)

MIN_HEIGHT = 4


def browse(root: str) -> int:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        sys.stderr.write("browse requires a terminal\n")
        return 2
    if _stdout_height() < MIN_HEIGHT:
        sys.stderr.write("terminal too small\n")
        return 2
    try:
        raw = _read_dust(root)
        tree = parse_tree(raw, root)
    except ScanError as exc:
        if str(exc):
            sys.stderr.write(f"{exc}\n")
        return 2
    except KeyboardInterrupt:
        return 2
    try:
        return curses.wrapper(_loop, tree)
    except KeyboardInterrupt:
        return 0


def _stdout_height() -> int:
    try:
        return os.get_terminal_size(sys.stdout.fileno()).lines
    except OSError:
        return 0


def _read_dust(root: str) -> str:
    try:
        process = subprocess.Popen(
            dust_browse_argv("dust", root),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        raise ScanError("dust not found") from exc
    saw_stderr = False

    def drain() -> None:
        nonlocal saw_stderr
        assert process.stderr is not None
        while True:
            chunk = process.stderr.read(1024)
            if not chunk:
                break
            saw_stderr = True
            sys.stderr.buffer.write(chunk)
            sys.stderr.buffer.flush()

    thread = threading.Thread(target=drain)
    thread.start()
    try:
        assert process.stdout is not None
        raw = process.stdout.read()
        code = process.wait()
        thread.join()
    except KeyboardInterrupt:
        process.kill()
        process.wait()
        thread.join()
        raise
    if code != 0:
        if not saw_stderr:
            raise ScanError("dust failed")
        raise ScanError("")
    try:
        return raw.decode()
    except UnicodeDecodeError as exc:
        raise ScanError("dust json is invalid") from exc


def _loop(stdscr: curses.window, root: TreeNode) -> int:
    curses.curs_set(0)
    stdscr.keypad(True)
    state = initial_state(root)
    while True:
        height, width = stdscr.getmaxyx()
        state = clamp_selected(state, height)
        _draw(stdscr, state, height, width)
        try:
            key = stdscr.getch()
        except KeyboardInterrupt:
            mapped = "ctrl-c"
        else:
            mapped = _map_key(key)
        if mapped is None and state.pending_path is None and state.notice is None:
            continue
        if mapped is None and state.pending_path is not None:
            mapped = "ignore"
        is_dir = _selected_is_dir(state, height)
        effect = apply_key(state, mapped or "ignore", is_dir=is_dir, height=height)
        if effect.quit:
            return 0
        state = effect.state
        if effect.trash_path is None:
            continue
        try:
            move_to_trash(effect.trash_path)
        except TrashError as exc:
            state = BrowseState(state.stack, state.selected, None, str(exc))
            continue
        state = clamp_selected(drop_child(state, effect.trash_path), height)


def _selected_is_dir(state: BrowseState, height: int) -> bool:
    rows = visible_rows(state.stack[-1], height)
    if not rows or state.selected >= len(rows):
        return False
    row = rows[state.selected]
    if row.kind != "entry" or row.path is None:
        return False
    try:
        return Path(row.path).is_dir()
    except OSError:
        return False


def _draw(stdscr: curses.window, state: BrowseState, height: int, width: int) -> None:
    stdscr.erase()
    if height < MIN_HEIGHT or width < 1:
        stdscr.refresh()
        return
    node = state.stack[-1]
    rows = visible_rows(node, height)
    size_width = size_column_width(rows)
    _put(stdscr, 0, render_path(node.path, width), width, curses.A_NORMAL)
    _put(stdscr, 1, render_header(width, size_width), width, curses.A_NORMAL)
    for index, row in enumerate(rows):
        attr = curses.A_REVERSE if index == state.selected else curses.A_NORMAL
        _put(
            stdscr,
            2 + index,
            render_row(row, width, size_width, is_dir=_dir_flag(row)),
            width,
            attr,
        )
    selected = rows[state.selected] if rows else None
    _put(
        stdscr,
        height - 1,
        status_line(state, selected, is_dir=_dir_flag(selected) if selected else False),
        width,
        curses.A_NORMAL,
    )
    stdscr.refresh()


def _dir_flag(row: Row) -> bool:
    if row.kind != "entry" or row.path is None:
        return False
    try:
        return Path(row.path).is_dir()
    except OSError:
        return False


def _put(stdscr: curses.window, y: int, text: str, width: int, attr: int) -> None:
    try:
        stdscr.addnstr(y, 0, text, width, attr)
    except curses.error:
        return


def _map_key(key: int) -> str | None:
    if key == curses.KEY_UP:
        return "up"
    if key == curses.KEY_DOWN:
        return "down"
    if key in {curses.KEY_ENTER, 10, 13}:
        return "enter"
    if key in {curses.KEY_BACKSPACE, curses.KEY_LEFT, 127, 8}:
        return "backspace"
    if key == ord("q") or key == 3:
        return "quit"
    if key == ord("d"):
        return "d"
    if key == ord("y"):
        return "y"
    return None
