import json
from collections.abc import Callable
from dataclasses import dataclass

from dustsweeper.model import Card

NARRATE_INSTRUCTION = (
    "이 카드 하나만 한국어 한 단락으로 설명하라. 파일 내용은 주어지지 않았다. "
    "삭제, rm, unlink, trash, 휴지통을 제안하지 마라. 사용 중이 아니라고 단정하지 마라."
)
REFUSAL_DELETE = "서술을 거절함. 삭제 지시가 포함되어 있음."
REFUSAL_FAILED = "서술을 거절함. 명령이 실패함."
NARRATE_TIMEOUT_SEC = 30

_LATIN_NEEDLES = ("rm ", "unlink", "trash")
_KOREAN_NEEDLES = ("지워", "지워도", "삭제해")


class NarrateError(Exception):
    pass


@dataclass(frozen=True)
class Narration:
    path: str
    text_ko: str
    source: str


def cards_for_narration(cards: tuple[Card, ...]) -> tuple[Card, ...]:
    return tuple(card for card in cards if card.identity.rule_id is None)


def narration_stdin(card: Card) -> str:
    payload = {
        "instruction": NARRATE_INSTRUCTION,
        "card": {
            "daemon_commands": list(card.evidence.daemon_commands),
            "last_used": card.evidence.last_used,
            "open_commands": [item.command for item in card.evidence.open_files],
            "path": card.path,
            "size_bytes": card.size_bytes,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def accept_narration(path: str, text: str) -> Narration:
    folded = text.casefold()
    if any(needle in folded for needle in _LATIN_NEEDLES) or any(
        needle in text for needle in _KOREAN_NEEDLES
    ):
        return Narration(path, REFUSAL_DELETE, "refused")
    return Narration(path, text.strip(), "llm")


def narrate_card(card: Card, runner: Callable[[str], str]) -> Narration:
    if card.identity.rule_id is not None:
        raise NarrateError("matched card")
    try:
        text = runner(narration_stdin(card))
    except NarrateError:
        return Narration(card.path, REFUSAL_FAILED, "refused")
    return accept_narration(card.path, text)
