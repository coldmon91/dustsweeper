from pathlib import Path

import pytest

from dustsweeper.model import Candidate, Node, ScanError
from dustsweeper.scan import (
    dust_argv,
    parse_dust_json,
    parse_size_bytes,
    scan_roots,
    select_candidates,
)


def test_dust_argv_is_byte_json_on_stdout():
    assert dust_argv("dust", "/tmp/scan", 1) == [
        "dust", "-j", "-o", "b", "-P", "-d", "1", "--", "/tmp/scan"
    ]


def test_parse_size_bytes_accepts_only_byte_suffix():
    assert parse_size_bytes("208896B") == 208896
    with pytest.raises(ScanError, match="dust size is not bytes: 4.0Ki"):
        parse_size_bytes("4.0Ki")


def test_parse_dust_json_joins_relative_names():
    raw = Path("tests/fixtures/dust-bytes.json").read_text()
    nodes = parse_dust_json(raw, "/tmp/scan")
    assert Node(path="/tmp/scan", size_bytes=208896, depth=0) in nodes
    assert Node(path="/tmp/scan/keep", size_bytes=204800, depth=1) in nodes
    assert Node(path="/tmp/scan/drop.bin", size_bytes=4096, depth=1) in nodes


def test_select_drops_root_and_small_files():
    nodes = (
        Node(path="/tmp/scan", size_bytes=208896, depth=0),
        Node(path="/tmp/scan/keep", size_bytes=204800, depth=1),
        Node(path="/tmp/scan/drop.bin", size_bytes=4096, depth=1),
    )
    assert select_candidates(nodes, min_bytes=100000, limit=50) == (
        Candidate(path="/tmp/scan/keep", size_bytes=204800, depth=1),
    )


def test_select_breaks_ties_by_path():
    nodes = (
        Node(path="/tmp/scan/b", size_bytes=100, depth=1),
        Node(path="/tmp/scan/a", size_bytes=100, depth=1),
    )
    selected = select_candidates(nodes, min_bytes=1, limit=1)
    assert selected == (Candidate(path="/tmp/scan/a", size_bytes=100, depth=1),)


def test_scan_roots_records_argv_and_applies_limit_once():
    seen = []

    def runner(argv):
        seen.append(argv)
        if argv[-1] == "/tmp/big":
            return '{"size":"300B","name":".","children":[{"size":"300B","name":"./big","children":[]}]}'
        return '{"size":"100B","name":".","children":[{"size":"100B","name":"./small","children":[]}]}'

    selected = scan_roots(("/tmp/small", "/tmp/big"), 1, 1, 1, runner)
    assert seen[0] == ["dust", "-j", "-o", "b", "-P", "-d", "1", "--", "/tmp/small"]
    assert selected == (Candidate(path="/tmp/big/big", size_bytes=300, depth=1),)
