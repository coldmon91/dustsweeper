import json

from dustsweeper.model import (
    REPORT_VERSION,
    Candidate,
    Card,
    Evidence,
    Identity,
    OpenFile,
)
from dustsweeper.narrate import Narration


def dumps(payload: dict[str, object]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def render_scan(candidates: tuple[Candidate, ...], min_bytes: int) -> str:
    payload = {
        "version": REPORT_VERSION,
        "min_bytes": min_bytes,
        "candidates": [_candidate_payload(item) for item in candidates],
    }
    return dumps(payload)


def load_candidates(raw: str) -> tuple[Candidate, ...]:
    payload = json.loads(raw)
    return tuple(
        Candidate(path=item["path"], size_bytes=item["size_bytes"], depth=item["depth"])
        for item in payload["candidates"]
    )


def render_cards(cards: tuple[Card, ...], min_bytes: int) -> str:
    payload = {
        "version": REPORT_VERSION,
        "min_bytes": min_bytes,
        "candidates": [_card_payload(item) for item in cards],
    }
    return dumps(payload)


def load_cards(raw: str) -> tuple[Card, ...]:
    payload = json.loads(raw)
    return tuple(_card_from_payload(item) for item in payload["candidates"])


def render_narrated(
    cards: tuple[Card, ...],
    narrations: dict[str, Narration],
    min_bytes: int,
) -> str:
    candidates = []
    for item in cards:
        body = _card_payload(item)
        narration = narrations.get(item.path)
        if narration is None:
            body["narration"] = None
        else:
            body["narration"] = {"source": narration.source, "text_ko": narration.text_ko}
        candidates.append(body)
    return dumps({"version": REPORT_VERSION, "min_bytes": min_bytes, "candidates": candidates})


def _card_from_payload(item: dict[str, object]) -> Card:
    evidence = item["evidence"]
    identity = item["identity"]
    if not isinstance(evidence, dict) or not isinstance(identity, dict):
        raise TypeError("card payload")
    opened = evidence["open_files"]
    if not isinstance(opened, list):
        raise TypeError("open_files")
    return Card(
        path=str(item["path"]),
        size_bytes=_as_int(item["size_bytes"]),
        depth=_as_int(item["depth"]),
        evidence=Evidence(
            open_files=tuple(
                OpenFile(pid=_as_int(row["pid"]), command=str(row["command"]), path=str(row["path"]))
                for row in opened
                if isinstance(row, dict)
            ),
            daemon_commands=tuple(str(command) for command in evidence["daemon_commands"]),
            last_used=None if evidence["last_used"] is None else str(evidence["last_used"]),
        ),
        identity=Identity(
            rule_id=None if identity["rule_id"] is None else str(identity["rule_id"]),
            kind=str(identity["kind"]),
            label_ko=str(identity["label_ko"]),
            touch=str(identity["touch"]),
        ),
    )


def _as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("expected int")
    return value


def _candidate_payload(item: Candidate | Card) -> dict[str, object]:
    return {"path": item.path, "size_bytes": item.size_bytes, "depth": item.depth}


def _card_payload(item: Card) -> dict[str, object]:
    body = _candidate_payload(item)
    body["evidence"] = {
        "open_files": [
            {"pid": opened.pid, "command": opened.command, "path": opened.path}
            for opened in item.evidence.open_files
        ],
        "daemon_commands": list(item.evidence.daemon_commands),
        "last_used": item.evidence.last_used,
    }
    body["identity"] = {
        "rule_id": item.identity.rule_id,
        "kind": item.identity.kind,
        "label_ko": item.identity.label_ko,
        "touch": item.identity.touch,
    }
    return body
