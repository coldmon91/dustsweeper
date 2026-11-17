from dataclasses import dataclass

MIN_BYTES_DEFAULT = 1_073_741_824
DEPTH_DEFAULT = 2
CANDIDATE_LIMIT_DEFAULT = 50
REPORT_VERSION = 1


class ScanError(Exception):
    pass


@dataclass(frozen=True)
class Node:
    path: str
    size_bytes: int
    depth: int


@dataclass(frozen=True)
class Candidate:
    path: str
    size_bytes: int
    depth: int


@dataclass(frozen=True)
class OpenFile:
    pid: int
    command: str
    path: str


@dataclass(frozen=True)
class Evidence:
    open_files: tuple[OpenFile, ...]
    daemon_commands: tuple[str, ...]
    last_used: str | None


@dataclass(frozen=True)
class Identity:
    rule_id: str | None
    kind: str
    label_ko: str
    touch: str


@dataclass(frozen=True)
class Rule:
    rule_id: str
    suffix: str
    kind: str
    label_ko: str
    touch: str
    live_basenames: tuple[str, ...]
    observe_basenames: tuple[str, ...]


@dataclass(frozen=True)
class Card:
    path: str
    size_bytes: int
    depth: int
    evidence: Evidence
    identity: Identity
