import json

import pytest

from dustsweeper.model import Card, Evidence, Identity, OpenFile
from dustsweeper.narrate import (
    NARRATE_TIMEOUT_SEC,
    NarrateError,
    Narration,
    accept_narration,
    cards_for_narration,
    narrate_card,
    narration_stdin,
)


def test_only_unmatched_cards_are_sent():
    matched = Card(
        "/Users/cskim/.ollama", 10, 1,
        Evidence((), ("/usr/local/bin/ollama",), "2026-10-19T09:53:41Z"),
        Identity("ollama_models", "model_store", "모델 저장소", "report_only"),
    )
    unknown = Card(
        "/Users/cskim/.cache/codex-runtimes", 20, 2,
        Evidence((OpenFile(1, "codex", "/Users/cskim/.cache/codex-runtimes/lock"),), (), None),
        Identity(None, "unknown", "", "unknown"),
    )
    assert cards_for_narration((matched, unknown)) == (unknown,)


def test_stdin_has_only_one_card():
    unknown = Card(
        "/Users/cskim/.cache/codex-runtimes", 20, 2,
        Evidence((OpenFile(1, "codex", "/Users/cskim/.cache/codex-runtimes/lock"),), (), None),
        Identity(None, "unknown", "", "unknown"),
    )
    payload = json.loads(narration_stdin(unknown))
    assert set(payload) == {"card", "instruction"}
    assert payload["instruction"] == (
        "이 카드 하나만 한국어 한 단락으로 설명하라. 파일 내용은 주어지지 않았다. "
        "삭제, rm, unlink, trash, 휴지통을 제안하지 마라. 사용 중이 아니라고 단정하지 마라."
    )
    assert payload["card"] == {
        "daemon_commands": [],
        "last_used": None,
        "open_commands": ["codex"],
        "path": "/Users/cskim/.cache/codex-runtimes",
        "size_bytes": 20,
    }
    assert "/Users/cskim/.ollama" not in narration_stdin(unknown)


def test_accepts_plain_korean():
    got = accept_narration("/tmp/unknown", "이 경로는 정체를 규칙으로 확정하지 못했다.")
    assert got.source == "llm"
    assert got.text_ko == "이 경로는 정체를 규칙으로 확정하지 못했다."


def test_allows_sentence_that_denies_deletion():
    got = accept_narration("/tmp/unknown", "삭제 명령은 없다")
    assert got.source == "llm"


def test_refuses_delete_advice_and_rm_any_case():
    assert accept_narration("/tmp/unknown", "지워도 됩니다").text_ko == (
        "서술을 거절함. 삭제 지시가 포함되어 있음."
    )
    assert accept_narration("/tmp/unknown", "RM -rf /tmp").source == "refused"


def test_failed_command_is_refused():
    unknown = Card(
        "/tmp/unknown", 10, 1, Evidence((), (), None),
        Identity(None, "unknown", "", "unknown"),
    )

    def runner(stdin: str) -> str:
        raise NarrateError("exit 1")

    got = narrate_card(unknown, runner)
    assert got == Narration(
        "/tmp/unknown", "서술을 거절함. 명령이 실패함.", "refused"
    )


def test_timeout_constant():
    assert NARRATE_TIMEOUT_SEC == 30


def test_narrate_card_rejects_matched_card():
    matched = Card(
        "/Users/cskim/.ollama", 10, 1, Evidence((), (), None),
        Identity("ollama_models", "model_store", "모델 저장소", "report_only"),
    )

    def runner(stdin: str) -> str:
        raise AssertionError("sent")

    with pytest.raises(NarrateError):
        narrate_card(matched, runner)
