import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from dustsweeper.model import ScanError

SIZE_COLUMN_MIN = 10
PERCENT_COLUMN = 4
COLUMN_GAP = 2
CHROME_ROWS = 3
ELLIPSIS = "..."

_KEEP = object()
_UNITS = ("B", "KiB", "MiB", "GiB", "TiB")


@dataclass(frozen=True)
class TreeNode:
    path: str
    size_bytes: int
    children: tuple["TreeNode", ...]


@dataclass(frozen=True)
class Row:
    kind: str
    name: str
    size_bytes: int
    percent: int
    path: str | None


@dataclass(frozen=True)
class BrowseState:
    stack: tuple[TreeNode, ...]
    selected: int
    pending_path: str | None = None
    notice: str | None = None


@dataclass(frozen=True)
class KeyEffect:
    state: BrowseState
    quit: bool = False
    trash_path: str | None = None


def dust_browse_argv(binary: str, root: str) -> list[str]:
    return [binary, "-j", "-o", "b", "--", root]


def parse_tree(raw: str, root: str) -> TreeNode:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScanError("dust json is invalid") from exc
    if not isinstance(payload, dict):
        raise ScanError("dust json is invalid")
    return _node(payload, root)


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes}B"
    scale = 1024
    for unit in _UNITS[1:]:
        if size_bytes < scale * 1024 or unit == "TiB":
            text = f"{size_bytes / scale:.1f}".removesuffix(".0")
            return f"{text}{unit}"
        scale *= 1024
    return f"{size_bytes}B"


def percent(part: int, whole: int) -> int:
    if whole == 0:
        return 0
    return (part * 100 + whole // 2) // whole


def visible_rows(node: TreeNode, height: int) -> tuple[Row, ...]:
    slots = height - CHROME_ROWS
    if slots < 1:
        return ()
    children = node.children
    if len(children) <= slots:
        shown = children
        hidden: tuple[TreeNode, ...] = ()
    elif slots == 1:
        shown = children[:1]
        hidden = ()
    else:
        shown = children[: slots - 1]
        hidden = children[len(shown) :]
    rows = [
        Row(
            kind="entry",
            name=Path(child.path).name,
            size_bytes=child.size_bytes,
            percent=percent(child.size_bytes, node.size_bytes),
            path=child.path,
        )
        for child in shown
    ]
    if hidden:
        rest_size = sum(child.size_bytes for child in hidden)
        rows.append(
            Row(
                kind="rest",
                name=f"나머지 {len(hidden)}개",
                size_bytes=rest_size,
                percent=percent(rest_size, node.size_bytes),
                path=None,
            )
        )
    return tuple(rows)


def initial_state(root: TreeNode) -> BrowseState:
    return BrowseState((root,), 0)


def clamp_selected(state: BrowseState, height: int) -> BrowseState:
    count = len(visible_rows(state.stack[-1], height))
    if count == 0 or state.selected < 0:
        return _copy(state, selected=0)
    if state.selected >= count:
        return _copy(state, selected=count - 1)
    return state


def apply_key(state: BrowseState, key: str, *, is_dir: bool, height: int) -> KeyEffect:
    if state.pending_path is not None:
        return _confirm(state, key, height)
    state = _copy(state, clear_notice=True)
    rows = visible_rows(state.stack[-1], height)
    if key in {"quit", "ctrl-c"}:
        return KeyEffect(state, quit=True)
    if key == "up":
        return KeyEffect(_copy(state, selected=max(0, state.selected - 1)))
    if key == "down":
        last = max(0, len(rows) - 1)
        return KeyEffect(_copy(state, selected=min(last, state.selected + 1)))
    if key == "backspace":
        if len(state.stack) == 1:
            return KeyEffect(state)
        return KeyEffect(_copy(state, stack=state.stack[:-1], selected=0))
    if key == "enter":
        if not rows or rows[state.selected].kind != "entry" or not is_dir:
            return KeyEffect(state)
        child = _child(state.stack[-1], rows[state.selected].path)
        if child is None:
            return KeyEffect(state)
        return KeyEffect(_copy(state, stack=state.stack + (child,), selected=0))
    if key == "d":
        path = _selected_entry_path(state, height)
        if path is None:
            return KeyEffect(state)
        return KeyEffect(_copy(state, pending_path=path))
    return KeyEffect(state)


def drop_child(state: BrowseState, path: str) -> BrowseState:
    current = state.stack[-1]
    removed = next((child for child in current.children if child.path == path), None)
    if removed is None:
        return _copy(state, clear_pending=True)
    updated = TreeNode(
        path=current.path,
        size_bytes=max(0, current.size_bytes - removed.size_bytes),
        children=tuple(child for child in current.children if child.path != path),
    )
    stack = list(state.stack)
    stack[-1] = updated
    for index in range(len(stack) - 2, -1, -1):
        parent = stack[index]
        child = stack[index + 1]
        stack[index] = TreeNode(
            path=parent.path,
            size_bytes=max(0, parent.size_bytes - removed.size_bytes),
            children=tuple(
                child if item.path == child.path else item for item in parent.children
            ),
        )
    return BrowseState(tuple(stack), state.selected, None, state.notice)


def status_line(state: BrowseState, row: Row | None, *, is_dir: bool) -> str:
    if state.pending_path is not None:
        name = ""
        if row is not None and row.path == state.pending_path:
            name = row.name + "/" if is_dir else row.name
        return f"휴지통으로 옮길까요? {name}  y"
    if state.notice:
        return state.notice
    return render_status(row)


def _confirm(state: BrowseState, key: str, height: int) -> KeyEffect:
    cleared = _copy(state, clear_pending=True)
    if key != "y":
        return KeyEffect(cleared)
    selected = _selected_entry_path(state, height)
    if selected != state.pending_path:
        return KeyEffect(cleared)
    return KeyEffect(cleared, trash_path=state.pending_path)


def _selected_entry_path(state: BrowseState, height: int) -> str | None:
    rows = visible_rows(state.stack[-1], height)
    if not rows or state.selected >= len(rows):
        return None
    row = rows[state.selected]
    if row.kind != "entry":
        return None
    return row.path


def _copy(
    state: BrowseState,
    *,
    stack: tuple[TreeNode, ...] | None = None,
    selected: int | None = None,
    pending_path: str | None = None,
    notice: str | None = None,
    clear_pending: bool = False,
    clear_notice: bool = False,
) -> BrowseState:
    return BrowseState(
        state.stack if stack is None else stack,
        state.selected if selected is None else selected,
        None
        if clear_pending
        else (pending_path if pending_path is not None else state.pending_path),
        None if clear_notice else (notice if notice is not None else state.notice),
    )


def display_width(text: str) -> int:
    width = 0
    for char in text:
        width += 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
    return width


def fit_head(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return text
    return _fit(text, width, keep_end=False)


def fit_tail(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return text
    return _fit(text, width, keep_end=True)


def size_column_width(rows: tuple[Row, ...]) -> int:
    widest = SIZE_COLUMN_MIN
    for row in rows:
        widest = max(widest, display_width(format_size(row.size_bytes)))
    return widest


def render_path(path: str, width: int) -> str:
    return fit_tail(path, width)


def render_header(width: int, size_width: int) -> str:
    return _columns("이름", "크기", "비율", width, size_width)


def render_row(row: Row, width: int, size_width: int, *, is_dir: bool) -> str:
    name = row.name + "/" if is_dir and row.kind == "entry" else row.name
    return _columns(
        name, format_size(row.size_bytes), f"{row.percent}%", width, size_width
    )


def render_status(row: Row | None) -> str:
    if row is None:
        return ""
    return f"{format_size(row.size_bytes)}  {row.percent}%"


def _columns(
    name: str, size_text: str, percent_text: str, width: int, size_width: int
) -> str:
    name_width = width - size_width - PERCENT_COLUMN - COLUMN_GAP * 2
    name_width = max(name_width, 0)
    fitted = pad_display(fit_head(name, name_width), name_width)
    size_cell = pad_left(size_text, size_width)
    percent_cell = pad_left(percent_text, PERCENT_COLUMN)
    return fit_tail(
        f"{fitted}{' ' * COLUMN_GAP}{size_cell}{' ' * COLUMN_GAP}{percent_cell}", width
    )


def pad_display(text: str, width: int) -> str:
    return _pad(text, width, left=False)


def pad_left(text: str, width: int) -> str:
    return _pad(text, width, left=True)


def _pad(text: str, width: int, *, left: bool) -> str:
    gap = width - display_width(text)
    if gap <= 0:
        return text
    spaces = " " * gap
    return spaces + text if left else text + spaces


def _fit(text: str, width: int, *, keep_end: bool) -> str:
    if display_width(ELLIPSIS) > width:
        return _take(ELLIPSIS, width, keep_end=False)
    body = _take(text, width - display_width(ELLIPSIS), keep_end=keep_end)
    if keep_end:
        return ELLIPSIS + body
    return body + ELLIPSIS


def _take(text: str, width: int, *, keep_end: bool) -> str:
    if width <= 0:
        return ""
    chars = list(text)
    if keep_end:
        chars.reverse()
    taken: list[str] = []
    used = 0
    for char in chars:
        char_width = 2 if unicodedata.east_asian_width(char) in {"W", "F"} else 1
        if used + char_width > width:
            break
        taken.append(char)
        used += char_width
    if keep_end:
        taken.reverse()
    return "".join(taken)


def _node(item: dict[str, object], root: str) -> TreeNode:
    if "name" not in item or "size" not in item:
        raise ScanError("dust json is invalid")
    children = item.get("children") or []
    if not isinstance(children, list):
        raise ScanError("dust json is invalid")
    nodes = [_node(child, root) for child in children if isinstance(child, dict)]
    if len(nodes) != len(children):
        raise ScanError("dust json is invalid")
    nodes.sort(key=lambda node: (-node.size_bytes, node.path))
    return TreeNode(
        path=_join(root, str(item["name"])),
        size_bytes=_size(str(item["size"])),
        children=tuple(nodes),
    )


def _size(size: str) -> int:
    if len(size) < 2 or size[-1] != "B" or not size[:-1].isdigit():
        raise ScanError(f"dust size is not bytes: {size}")
    return int(size[:-1])


def _join(root: str, name: str) -> str:
    if name == ".":
        return _strip_slash(root)
    if name.startswith("/"):
        return _strip_slash(name)
    relative = name.removeprefix("./")
    return _strip_slash(str(Path(root) / relative))


def _strip_slash(path: str) -> str:
    if path == "/":
        return path
    return path.rstrip("/") or "/"


def _child(node: TreeNode, path: str | None) -> TreeNode | None:
    for child in node.children:
        if child.path == path:
            return child
    return None
