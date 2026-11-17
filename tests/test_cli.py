import json
from pathlib import Path

from dustsweeper.cli import main
from dustsweeper.evidence import build_cards
from dustsweeper.model import Candidate


def test_no_args_requires_terminal(capsys):
    assert main([]) == 2
    assert capsys.readouterr().err == "browse requires a terminal\n"


def test_delete_and_rm_are_rejected():
    assert main(["delete"]) == 2
    assert main(["rm"]) == 2


def test_usage_line(capsys):
    assert main(["nope"]) == 2
    assert (
        capsys.readouterr().err == "usage: dustsweeper {browse|scan|inspect|narrate}\n"
    )


def test_browse_rejects_two_roots(capsys):
    code = main(["browse", "--root", "/tmp/a", "--root", "/tmp/b"])
    assert code == 2
    assert (
        capsys.readouterr().err == "usage: dustsweeper {browse|scan|inspect|narrate}\n"
    )


def test_scan_fixture_stdout(capsys):
    code = main(
        [
            "scan",
            "--dust-json",
            "tests/fixtures/dust-bytes.json",
            "--root",
            "/tmp/scan",
            "--min-bytes",
            "100000",
            "--limit",
            "50",
            "--depth",
            "1",
        ]
    )
    assert code == 0
    assert (
        capsys.readouterr().out
        == """{
  "candidates": [
    {
      "depth": 1,
      "path": "/tmp/scan/keep",
      "size_bytes": 204800
    }
  ],
  "min_bytes": 100000,
  "version": 1
}
"""
    )


def test_human_size_is_usage_error(capsys):
    code = main(
        [
            "scan",
            "--dust-json",
            "tests/fixtures/dust-human.json",
            "--root",
            "/tmp/scan",
            "--min-bytes",
            "1",
            "--depth",
            "1",
        ]
    )
    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == "dust size is not bytes: 4.0Ki\n"


def test_dust_json_rejects_two_roots(capsys):
    code = main(
        [
            "scan",
            "--dust-json",
            "tests/fixtures/dust-bytes.json",
            "--root",
            "/tmp/a",
            "--root",
            "/tmp/b",
        ]
    )
    assert code == 2
    assert capsys.readouterr().err == "dust-json requires exactly one root\n"


def test_negative_min_bytes(capsys):
    code = main(["scan", "--root", "/tmp/scan", "--min-bytes", "-1"])
    assert code == 2
    assert capsys.readouterr().err == "min_bytes must be >= 0\n"


def test_negative_depth(capsys):
    code = main(["scan", "--root", "/tmp/scan", "--depth", "-1"])
    assert code == 2
    assert capsys.readouterr().err == "depth must be >= 0\n"


def test_src_has_no_delete_api():
    text = "\n".join(path.read_text() for path in Path("src").rglob("*.py"))
    for token in ("os.remove", "os.unlink", "shutil.rmtree", "send2trash"):
        assert token not in text


def test_build_cards_does_not_read_file_bytes(monkeypatch):
    lsof_text = Path("tests/fixtures/lsof-mixed.txt").read_text()
    ps_text = Path("tests/fixtures/ps-live.txt").read_text()
    mdls = json.loads(Path("tests/fixtures/mdls-two.json").read_text())

    def boom(*args, **kwargs):
        raise AssertionError("read")

    monkeypatch.setattr(Path, "read_bytes", boom)
    monkeypatch.setattr("builtins.open", boom)
    candidates = (
        Candidate("/Users/cskim/.ollama", 13958643712, 1),
        Candidate("/Users/cskim/Library/Developer/CoreSimulator", 17, 2),
    )
    cards = build_cards(candidates, lsof_text, ps_text, mdls)
    assert cards[0].identity.rule_id == "ollama_models"
    assert cards[0].evidence.open_files == ()
    assert cards[0].evidence.daemon_commands == ("/usr/local/bin/ollama",)
    assert cards[0].evidence.last_used == "2026-10-19T09:53:41Z"
    assert cards[0].identity.touch == "report_only"
    assert cards[1].identity.touch == "live"
    assert cards[1].evidence.daemon_commands == ("/usr/libexec/simdiskimaged",)


def test_inspect_report_does_not_run_dust(capsys):
    code = main(
        [
            "inspect",
            "--report",
            "tests/fixtures/scan-two.json",
            "--lsof",
            "tests/fixtures/lsof-mixed.txt",
            "--ps",
            "tests/fixtures/ps-live.txt",
            "--mdls",
            "tests/fixtures/mdls-two.json",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == 1
    assert "narration" not in payload["candidates"][0]
    assert payload["candidates"][0]["identity"]["rule_id"] == "ollama_models"
    assert payload["candidates"][1]["identity"]["touch"] == "live"


def test_report_and_root_are_exclusive(capsys):
    code = main(
        ["inspect", "--report", "tests/fixtures/scan-two.json", "--root", "/tmp"]
    )
    assert code == 2
    assert capsys.readouterr().err == "report and root are mutually exclusive\n"


def test_narrate_without_command(monkeypatch, capsys):
    monkeypatch.delenv("DUSTSWEEPER_NARRATE_CMD", raising=False)
    code = main(["narrate", "--report", "tests/fixtures/cards-mixed.json"])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == "DUSTSWEEPER_NARRATE_CMD is unset\n"


def test_narrate_sends_only_unknown(monkeypatch, capsys, tmp_path):
    captured = tmp_path / "stdin.json"
    monkeypatch.setenv(
        "DUSTSWEEPER_NARRATE_CMD", "python3 tests/fixtures/fake_narrate.py"
    )
    monkeypatch.setenv("FAKE_STDIN_PATH", str(captured))
    code = main(["narrate", "--report", "tests/fixtures/cards-mixed.json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    by_path = {item["path"]: item for item in payload["candidates"]}
    assert by_path["/Users/cskim/.ollama"]["narration"] is None
    assert by_path["/Users/cskim/.cache/codex-runtimes"]["narration"] == {
        "source": "llm",
        "text_ko": "정체를 규칙으로 확정하지 못했다.",
    }
    assert "/Users/cskim/.ollama" not in captured.read_text()


def test_narrate_refuses_delete_advice(monkeypatch, capsys):
    monkeypatch.setenv(
        "DUSTSWEEPER_NARRATE_CMD", "python3 tests/fixtures/fake_refuse.py"
    )
    code = main(["narrate", "--report", "tests/fixtures/cards-mixed.json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    unknown = next(
        item
        for item in payload["candidates"]
        if item["path"] == "/Users/cskim/.cache/codex-runtimes"
    )
    assert unknown["narration"]["source"] == "refused"
    assert (
        unknown["narration"]["text_ko"] == "서술을 거절함. 삭제 지시가 포함되어 있음."
    )


def test_src_has_no_network_client():
    text = "\n".join(path.read_text() for path in Path("src").rglob("*.py"))
    for token in ("urllib.request", "httpx", "openai", "socket.create_connection"):
        assert token not in text
