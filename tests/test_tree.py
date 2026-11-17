import json

import pytest

from dustsweeper.model import ScanError
from dustsweeper.tree import (
    apply_key,
    display_width,
    drop_child,
    dust_browse_argv,
    fit_head,
    fit_tail,
    format_size,
    initial_state,
    parse_tree,
    percent,
    render_header,
    render_row,
    render_status,
    status_line,
    visible_rows,
)


def test_browse_argv_has_no_depth_or_progress_flag():
    assert dust_browse_argv("dust", "/tmp/scan") == [
        "dust",
        "-j",
        "-o",
        "b",
        "--",
        "/tmp/scan",
    ]


def test_parse_tree_joins_root_and_sorts_by_size():
    raw = json.dumps(
        {
            "size": "100B",
            "name": ".",
            "children": [
                {"size": "10B", "name": "./small", "children": []},
                {
                    "size": "30B",
                    "name": "./big",
                    "children": [{"size": "25B", "name": "./big/leaf", "children": []}],
                },
                {"size": "20B", "name": "/abs/mid", "children": []},
            ],
        }
    )
    root = parse_tree(raw, "/tmp/scan/")
    assert root.path == "/tmp/scan"
    assert root.size_bytes == 100
    assert [child.path for child in root.children] == [
        "/tmp/scan/big",
        "/abs/mid",
        "/tmp/scan/small",
    ]
    assert root.children[0].children[0].path == "/tmp/scan/big/leaf"


def test_invalid_json_and_human_size():
    with pytest.raises(ScanError, match="dust json is invalid"):
        parse_tree("{", "/tmp/scan")
    with pytest.raises(ScanError, match="dust size is not bytes: 4.0Ki"):
        parse_tree('{"size":"4.0Ki","name":".","children":[]}', "/tmp/scan")


def test_format_size_and_percent_use_current_directory():
    assert format_size(61762732032) == "57.5GiB"
    assert format_size(1536) == "1.5KiB"
    assert format_size(1024) == "1KiB"
    assert format_size(1023) == "1023B"
    assert percent(30, 100) == 30
    assert percent(1, 0) == 0


def test_visible_rows_keep_only_what_fits():
    root = parse_tree(
        json.dumps(
            {
                "size": "100B",
                "name": ".",
                "children": [
                    {"size": "30B", "name": "./big", "children": []},
                    {"size": "20B", "name": "./mid", "children": []},
                    {"size": "10B", "name": "./small", "children": []},
                ],
            }
        ),
        "/tmp/scan",
    )
    one_slot = visible_rows(root, 4)
    assert [row.name for row in one_slot] == ["big"]
    two_slots = visible_rows(root, 5)
    assert two_slots[0].name == "big"
    assert two_slots[0].percent == 30
    assert two_slots[1].kind == "rest"
    assert two_slots[1].name == "나머지 2개"
    assert two_slots[1].size_bytes == 30
    assert two_slots[1].path is None
    assert [row.kind for row in visible_rows(root, 7)] == ["entry", "entry", "entry"]


def test_keys_enter_only_directories():
    root = parse_tree(
        json.dumps(
            {
                "size": "100B",
                "name": ".",
                "children": [
                    {
                        "size": "30B",
                        "name": "./big",
                        "children": [
                            {"size": "25B", "name": "./big/leaf", "children": []},
                        ],
                    },
                    {"size": "10B", "name": "./small", "children": []},
                ],
            }
        ),
        "/tmp/scan",
    )
    state = initial_state(root)
    stayed = apply_key(state, "enter", is_dir=False, height=8)
    assert stayed.quit is False
    assert stayed.state.stack == state.stack
    entered = apply_key(state, "enter", is_dir=True, height=8)
    assert entered.state.stack[-1].path == "/tmp/scan/big"
    assert entered.state.selected == 0
    back = apply_key(entered.state, "backspace", is_dir=False, height=8)
    assert back.state.stack == (root,)
    assert apply_key(state, "backspace", is_dir=False, height=8).state == state
    crowded = parse_tree(
        json.dumps(
            {
                "size": "100B",
                "name": ".",
                "children": [
                    {"size": "30B", "name": "./big", "children": []},
                    {"size": "20B", "name": "./mid", "children": []},
                    {"size": "10B", "name": "./small", "children": []},
                ],
            }
        ),
        "/tmp/scan",
    )
    rest_state = apply_key(initial_state(crowded), "down", is_dir=False, height=5).state
    assert visible_rows(crowded, 5)[rest_state.selected].kind == "rest"
    assert apply_key(rest_state, "enter", is_dir=True, height=5).state == rest_state
    assert apply_key(state, "quit", is_dir=False, height=8).quit is True


def test_fit_uses_display_width():
    assert fit_head("가나다", 4) == "..."
    assert fit_tail("/tmp/scan/keep", 8) == ".../keep"
    row = visible_rows(
        parse_tree(
            '{"size":"10B","name":".","children":[{"size":"10B","name":"./big","children":[]}]}',
            "/tmp/scan",
        ),
        6,
    )[0]
    assert render_row(row, 24, 10, is_dir=True).startswith("big/")
    assert render_status(None) == ""
    assert render_status(row) == "10B  100%"
    header = render_header(40, 10)
    assert display_width(header.rsplit("  ", 1)[-1]) == 4


def test_confirm_cancels_without_moving():
    root = parse_tree(
        json.dumps(
            {
                "size": "100B",
                "name": ".",
                "children": [
                    {"size": "30B", "name": "./big", "children": []},
                    {"size": "20B", "name": "./mid", "children": []},
                    {"size": "10B", "name": "./small", "children": []},
                ],
            }
        ),
        "/tmp/scan",
    )
    state = initial_state(root)
    armed = apply_key(state, "d", is_dir=True, height=8)
    assert armed.trash_path is None
    assert armed.state.pending_path == "/tmp/scan/big"
    row = visible_rows(root, 8)[0]
    assert status_line(armed.state, row, is_dir=True) == "휴지통으로 옮길까요? big/  y"
    requested = apply_key(armed.state, "y", is_dir=True, height=8)
    assert requested.trash_path == "/tmp/scan/big"
    assert requested.state.pending_path is None
    assert requested.state.stack == state.stack
    cancelled = apply_key(armed.state, "backspace", is_dir=True, height=8)
    assert cancelled.trash_path is None
    assert cancelled.quit is False
    assert cancelled.state.stack == state.stack
    assert cancelled.state.selected == state.selected
    assert cancelled.state.pending_path is None
    rest = apply_key(state, "down", is_dir=False, height=5).state
    assert apply_key(rest, "d", is_dir=False, height=5).state == rest


def test_drop_child_shrinks_ancestors():
    root = parse_tree(
        json.dumps(
            {
                "size": "130B",
                "name": ".",
                "children": [
                    {
                        "size": "100B",
                        "name": "./mid",
                        "children": [
                            {"size": "30B", "name": "./mid/leaf", "children": []}
                        ],
                    }
                ],
            }
        ),
        "/tmp/scan",
    )
    entered = apply_key(initial_state(root), "enter", is_dir=True, height=8).state
    dropped = drop_child(entered, "/tmp/scan/mid/leaf")
    assert dropped.stack[-1].size_bytes == 70
    assert dropped.stack[-1].children == ()
    assert dropped.stack[0].size_bytes == 100
    assert dropped.pending_path is None
