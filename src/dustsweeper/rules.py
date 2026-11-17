from pathlib import Path

from dustsweeper.model import Identity, Rule

RULES: tuple[Rule, ...] = (
    Rule("ollama_models", "/.ollama", "model_store", "모델 저장소", "report_only", (), ("ollama",)),
    Rule(
        "core_simulator",
        "/Library/Developer/CoreSimulator",
        "simulator",
        "시뮬레이터 이미지",
        "report_only",
        ("CoreSimulatorService", "simdiskimaged"),
        ("CoreSimulatorService", "simdiskimaged"),
    ),
    Rule(
        "claude_support",
        "/Library/Application Support/Claude",
        "app_support",
        "앱 지원 데이터",
        "report_only",
        ("Claude",),
        ("Claude",),
    ),
    Rule(
        "rancher_desktop",
        "/Library/Application Support/rancher-desktop",
        "app_support",
        "컨테이너 런타임 데이터",
        "report_only",
        (),
        ("Rancher Desktop", "rancher-desktop"),
    ),
    Rule("rsupport_docs", "/Documents/rsupport", "user_data", "사용자 데이터", "report_only", (), ()),
    Rule("downloads", "/Downloads", "user_data", "사용자 데이터", "report_only", (), ()),
    Rule("uv_cache", "/.cache/uv", "cache", "패키지 캐시", "reinstallable", (), ()),
    Rule("npm_cache", "/.npm", "cache", "패키지 캐시", "reinstallable", (), ()),
    Rule("trash", "/.Trash", "cache", "휴지통", "reinstallable", (), ()),
    Rule("rustup", "/.rustup", "toolchain", "툴체인", "reinstallable", (), ()),
    Rule(
        "homebrew_cache",
        "/Library/Caches/Homebrew",
        "cache",
        "패키지 캐시",
        "reinstallable",
        (),
        (),
    ),
    Rule("homebrew_cellar", "/Cellar", "toolchain", "패키지 설치본", "report_only", (), ()),
    Rule("app_bundle", ".app", "app_bundle", "앱 번들", "report_only", (), ()),
)

_UNKNOWN = Identity(None, "unknown", "", "unknown")


def path_matches(path: str, suffix: str) -> bool:
    normalized = path.rstrip("/")
    if suffix.startswith("."):
        return any(part.endswith(suffix) for part in normalized.split("/") if part)
    needle = suffix if suffix.startswith("/") else f"/{suffix}"
    start = 0
    while True:
        found = normalized.find(needle, start)
        if found < 0:
            return False
        after = found + len(needle)
        if after == len(normalized) or normalized[after] == "/":
            return True
        start = found + 1


def identity_for(path: str, processes: tuple[tuple[int, str], ...]) -> Identity:
    rule = _best_rule(path)
    if rule is None:
        return _UNKNOWN
    touch = rule.touch
    if _basename_running(rule.live_basenames, processes):
        touch = "live"
    return Identity(rule.rule_id, rule.kind, rule.label_ko, touch)


def observed_daemons(path: str, processes: tuple[tuple[int, str], ...]) -> tuple[str, ...]:
    rule = _best_rule(path)
    if rule is None:
        return ()
    names = set(rule.live_basenames) | set(rule.observe_basenames)
    hits = [(pid, command) for pid, command in processes if Path(command).name in names]
    hits.sort(key=lambda item: (item[1], item[0]))
    seen: set[str] = set()
    commands: list[str] = []
    for _pid, command in hits:
        if command in seen:
            continue
        seen.add(command)
        commands.append(command)
    return tuple(commands)


def _best_rule(path: str) -> Rule | None:
    matched = [rule for rule in RULES if path_matches(path, rule.suffix)]
    if not matched:
        return None
    matched.sort(key=lambda rule: (-len(rule.suffix), rule.rule_id))
    return matched[0]


def _basename_running(names: tuple[str, ...], processes: tuple[tuple[int, str], ...]) -> bool:
    wanted = set(names)
    return any(Path(command).name in wanted for _pid, command in processes)
