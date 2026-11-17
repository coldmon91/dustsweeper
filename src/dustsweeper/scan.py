import json
from collections.abc import Callable
from pathlib import Path

from dustsweeper.model import Candidate, Node, ScanError


def dust_argv(binary: str, root: str, depth: int) -> list[str]:
    return [binary, "-j", "-o", "b", "-P", "-d", str(depth), "--", root]


def parse_size_bytes(size: str) -> int:
    if len(size) < 2 or size[-1] != "B" or not size[:-1].isdigit():
        raise ScanError(f"dust size is not bytes: {size}")
    return int(size[:-1])


def parse_dust_json(raw: str, root: str) -> tuple[Node, ...]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ScanError(f"dust size is not bytes: {raw}") from exc
    nodes: list[Node] = []
    _walk(payload, root, 0, nodes)
    return tuple(nodes)


def select_candidates(
    nodes: tuple[Node, ...],
    min_bytes: int,
    limit: int,
) -> tuple[Candidate, ...]:
    chosen = [
        Candidate(path=node.path, size_bytes=node.size_bytes, depth=node.depth)
        for node in nodes
        if node.depth != 0 and node.size_bytes >= min_bytes
    ]
    chosen.sort(key=lambda item: (-item.size_bytes, item.path))
    return tuple(chosen[:limit])


def scan_roots(
    roots: tuple[str, ...],
    depth: int,
    min_bytes: int,
    limit: int,
    runner: Callable[[list[str]], str],
    binary: str = "dust",
) -> tuple[Candidate, ...]:
    nodes: list[Node] = []
    for root in roots:
        raw = runner(dust_argv(binary, root, depth))
        nodes.extend(parse_dust_json(raw, root))
    return select_candidates(tuple(nodes), min_bytes, limit)


def _walk(item: dict[str, object], root: str, depth: int, nodes: list[Node]) -> None:
    name = str(item["name"])
    nodes.append(
        Node(
            path=_join(root, name),
            size_bytes=parse_size_bytes(str(item["size"])),
            depth=depth,
        )
    )
    children = item.get("children") or []
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                _walk(child, root, depth + 1, nodes)


def _join(root: str, name: str) -> str:
    if name == ".":
        return root.rstrip("/") or root
    if name.startswith("/"):
        return name
    relative = name.removeprefix("./")
    return str(Path(root) / relative)
