import re

from dustsweeper.model import Candidate, Card, Evidence, OpenFile
from dustsweeper.rules import identity_for, observed_daemons

_LAST_USED = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) \+0000$")


def parse_lsof(text: str) -> tuple[OpenFile, ...]:
    pid = 0
    command = ""
    opened: list[OpenFile] = []
    for line in text.splitlines():
        if not line:
            continue
        kind, value = line[0], line[1:]
        if kind == "p":
            pid = int(value)
        elif kind == "c":
            command = value
        elif kind == "n" and value.startswith("/"):
            opened.append(OpenFile(pid=pid, command=command, path=value))
    return tuple(opened)


def open_files_for(candidate_path: str, opened: tuple[OpenFile, ...]) -> tuple[OpenFile, ...]:
    prefix = candidate_path.rstrip("/")
    return tuple(
        item for item in opened if item.path == prefix or item.path.startswith(prefix + "/")
    )


def parse_ps(text: str) -> tuple[tuple[int, str], ...]:
    rows: list[tuple[int, str]] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pid_text, _, command = stripped.partition(" ")
        rows.append((int(pid_text), command))
    return tuple(rows)


def parse_last_used(mdls_raw: str) -> str | None:
    match = _LAST_USED.fullmatch(mdls_raw.strip())
    if match is None:
        return None
    return f"{match.group(1)}T{match.group(2)}Z"


def build_cards(
    candidates: tuple[Candidate, ...],
    lsof_text: str,
    ps_text: str,
    mdls_by_path: dict[str, str],
) -> tuple[Card, ...]:
    opened = parse_lsof(lsof_text)
    processes = parse_ps(ps_text)
    cards: list[Card] = []
    for candidate in candidates:
        raw_date = mdls_by_path.get(candidate.path, "")
        cards.append(
            Card(
                path=candidate.path,
                size_bytes=candidate.size_bytes,
                depth=candidate.depth,
                evidence=Evidence(
                    open_files=open_files_for(candidate.path, opened),
                    daemon_commands=observed_daemons(candidate.path, processes),
                    last_used=parse_last_used(raw_date) if raw_date else None,
                ),
                identity=identity_for(candidate.path, processes),
            )
        )
    return tuple(cards)
