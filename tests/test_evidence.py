from dustsweeper.evidence import open_files_for, parse_last_used, parse_lsof, parse_ps
from dustsweeper.model import OpenFile


def test_ancestor_open_is_not_a_hit():
    text = "p58323\ncollama\nfcwd\nn/Users/cskim\nftxt\nn/usr/local/bin/ollama\n"
    opened = parse_lsof(text)
    assert open_files_for("/Users/cskim/.ollama", opened) == ()


def test_descendant_open_is_a_hit():
    text = (
        "p9047\ncClaude\nftxt\n"
        "n/Users/cskim/Library/Application Support/Claude/Local Storage/leveldb/LOCK\n"
    )
    opened = parse_lsof(text)
    assert open_files_for(
        "/Users/cskim/Library/Application Support/Claude", opened
    ) == (
        OpenFile(
            pid=9047,
            command="Claude",
            path="/Users/cskim/Library/Application Support/Claude/Local Storage/leveldb/LOCK",
        ),
    )


def test_ignores_non_path_names():
    assert parse_lsof("p1\ncx\nf1\nn->0xab\n") == ()


def test_parse_ps_strips_padding():
    assert parse_ps("  58323 /usr/local/bin/ollama\n") == (
        (58323, "/usr/local/bin/ollama"),
    )


def test_parse_last_used_utc_and_null():
    assert parse_last_used("2026-10-19 09:53:41 +0000") == "2026-10-19T09:53:41Z"
    assert parse_last_used("(null)") is None
    assert parse_last_used("") is None
    assert parse_last_used("2026-10-19 09:53:41 +0900") is None
