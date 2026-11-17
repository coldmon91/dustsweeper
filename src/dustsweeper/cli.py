import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

from dustsweeper.evidence import build_cards
from dustsweeper.model import (
    CANDIDATE_LIMIT_DEFAULT,
    DEPTH_DEFAULT,
    MIN_BYTES_DEFAULT,
    ScanError,
)
from dustsweeper.narrate import (
    NARRATE_TIMEOUT_SEC,
    NarrateError,
    cards_for_narration,
    narrate_card,
)
from dustsweeper.report import (
    load_candidates,
    load_cards,
    render_cards,
    render_narrated,
    render_scan,
)
from dustsweeper.scan import parse_dust_json, scan_roots, select_candidates
from dustsweeper.tui import browse

USAGE = "usage: dustsweeper {browse|scan|inspect|narrate}\n"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] == "browse":
        return _browse(args[1:] if args else [])
    if args[0] in {"delete", "rm"}:
        sys.stderr.write(USAGE)
        return 2
    if args[0] == "scan":
        return _scan(args[1:])
    if args[0] == "inspect":
        return _inspect(args[1:])
    if args[0] == "narrate":
        return _narrate(args[1:])
    sys.stderr.write(USAGE)
    return 2


def _browse(args: list[str]) -> int:
    root = os.getcwd()
    seen = 0
    index = 0
    while index < len(args):
        flag = args[index]
        if flag != "--root" or index + 1 >= len(args):
            sys.stderr.write(USAGE)
            return 2
        root = args[index + 1]
        seen += 1
        index += 2
    if seen > 1:
        sys.stderr.write(USAGE)
        return 2
    return browse(root)


def _scan(args: list[str]) -> int:
    parsed = _parse_scan_flags(args)
    if isinstance(parsed, int):
        return parsed
    roots, depth, min_bytes, limit, dust_json = parsed
    if not roots:
        sys.stderr.write(USAGE)
        return 2
    if depth < 0:
        sys.stderr.write("depth must be >= 0\n")
        return 2
    if min_bytes < 0:
        sys.stderr.write("min_bytes must be >= 0\n")
        return 2
    if dust_json is not None and len(roots) != 1:
        sys.stderr.write("dust-json requires exactly one root\n")
        return 2
    try:
        if dust_json is not None:
            raw = Path(dust_json).read_text()
            candidates = select_candidates(
                parse_dust_json(raw, roots[0]), min_bytes, limit
            )
        else:
            candidates = scan_roots(tuple(roots), depth, min_bytes, limit, _run_dust)
    except ScanError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    sys.stdout.write(render_scan(candidates, min_bytes))
    return 0


def _inspect(args: list[str]) -> int:
    parsed = _parse_inspect_flags(args)
    if isinstance(parsed, int):
        return parsed
    roots, depth, min_bytes, limit, report, lsof_path, ps_path, mdls_path = parsed
    if report is not None and roots:
        sys.stderr.write("report and root are mutually exclusive\n")
        return 2
    if report is None and not roots:
        sys.stderr.write(USAGE)
        return 2
    if depth < 0:
        sys.stderr.write("depth must be >= 0\n")
        return 2
    if min_bytes < 0:
        sys.stderr.write("min_bytes must be >= 0\n")
        return 2
    try:
        if report is not None:
            raw = Path(report).read_text()
            candidates = load_candidates(raw)
            min_bytes = int(json.loads(raw)["min_bytes"])
        else:
            candidates = scan_roots(tuple(roots), depth, min_bytes, limit, _run_dust)
        lsof_text = _read_or_run(lsof_path, ["lsof", "-F", "pcn"])
        ps_text = _read_or_run(ps_path, ["ps", "-axo", "pid=,comm="])
        if mdls_path is not None:
            mdls_by_path = json.loads(Path(mdls_path).read_text())
        else:
            mdls_by_path = {item.path: _mdls(item.path) for item in candidates}
        cards = build_cards(candidates, lsof_text, ps_text, mdls_by_path)
    except ScanError as exc:
        sys.stderr.write(f"{exc}\n")
        return 2
    sys.stdout.write(render_cards(cards, min_bytes))
    return 0


def _parse_scan_flags(
    args: list[str],
) -> tuple[list[str], int, int, int, str | None] | int:
    return _parse_flags(args, allow_report=False)


def _parse_inspect_flags(
    args: list[str],
) -> (
    tuple[list[str], int, int, int, str | None, str | None, str | None, str | None]
    | int
):
    return _parse_flags(args, allow_report=True)


def _parse_flags(args: list[str], allow_report: bool):
    roots: list[str] = []
    depth = DEPTH_DEFAULT
    min_bytes = MIN_BYTES_DEFAULT
    limit = CANDIDATE_LIMIT_DEFAULT
    dust_json: str | None = None
    report: str | None = None
    lsof_path: str | None = None
    ps_path: str | None = None
    mdls_path: str | None = None
    known = {"--root", "--depth", "--min-bytes", "--limit", "--dust-json"}
    if allow_report:
        known |= {"--report", "--lsof", "--ps", "--mdls"}
    index = 0
    while index < len(args):
        flag = args[index]
        if flag not in known or index + 1 >= len(args):
            sys.stderr.write(USAGE)
            return 2
        value = args[index + 1]
        index += 2
        if flag == "--root":
            roots.append(value)
        elif flag == "--dust-json":
            dust_json = value
        elif flag == "--report":
            report = value
        elif flag == "--lsof":
            lsof_path = value
        elif flag == "--ps":
            ps_path = value
        elif flag == "--mdls":
            mdls_path = value
        else:
            try:
                number = int(value)
            except ValueError:
                sys.stderr.write(USAGE)
                return 2
            if flag == "--depth":
                depth = number
            elif flag == "--min-bytes":
                min_bytes = number
            else:
                limit = number
    if allow_report:
        return roots, depth, min_bytes, limit, report, lsof_path, ps_path, mdls_path
    return roots, depth, min_bytes, limit, dust_json


def _narrate(args: list[str]) -> int:
    report = _flag_value(args, "--report")
    if report is None:
        sys.stderr.write(USAGE)
        return 2
    if not os.environ.get("DUSTSWEEPER_NARRATE_CMD"):
        sys.stderr.write("DUSTSWEEPER_NARRATE_CMD is unset\n")
        return 2
    raw = Path(report).read_text()
    cards = load_cards(raw)
    narrations = {
        card.path: narrate_card(card, _run_narrate)
        for card in cards_for_narration(cards)
    }
    min_bytes = int(json.loads(raw)["min_bytes"])
    sys.stdout.write(render_narrated(cards, narrations, min_bytes))
    return 0


def _flag_value(args: list[str], flag: str) -> str | None:
    for index, item in enumerate(args):
        if item == flag and index + 1 < len(args):
            return args[index + 1]
    return None


def _run_narrate(stdin: str) -> str:
    command = os.environ.get("DUSTSWEEPER_NARRATE_CMD", "")
    argv = shlex.split(command)
    try:
        completed = subprocess.run(
            argv,
            input=stdin,
            text=True,
            capture_output=True,
            timeout=NARRATE_TIMEOUT_SEC,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise NarrateError("timeout") from exc
    if completed.returncode != 0:
        raise NarrateError(f"exit {completed.returncode}")
    return completed.stdout


def _read_or_run(path: str | None, argv: list[str]) -> str:
    if path is not None:
        return Path(path).read_text()
    return _run_text(argv)


def _mdls(path: str) -> str:
    return _run_text(["mdls", "-name", "kMDItemLastUsedDate", "-raw", path])


def _run_text(argv: list[str]) -> str:
    completed = subprocess.run(argv, check=False, capture_output=True, text=True)
    return completed.stdout


def _run_dust(argv: list[str]) -> str:
    completed = subprocess.run(argv, check=False, capture_output=True, text=True)
    if completed.returncode != 0:
        message = completed.stderr.strip() or "dust failed"
        raise ScanError(message)
    return completed.stdout
