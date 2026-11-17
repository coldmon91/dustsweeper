from dustsweeper.model import Identity
from dustsweeper.rules import RULES, identity_for, observed_daemons


def test_rule_table_has_the_spec_ids():
    assert tuple(rule.rule_id for rule in RULES) == (
        "ollama_models",
        "core_simulator",
        "claude_support",
        "rancher_desktop",
        "rsupport_docs",
        "downloads",
        "uv_cache",
        "npm_cache",
        "trash",
        "rustup",
        "homebrew_cache",
        "homebrew_cellar",
        "app_bundle",
    )
    by_id = {rule.rule_id: rule for rule in RULES}
    assert by_id["ollama_models"].observe_basenames == ("ollama",)
    assert by_id["ollama_models"].live_basenames == ()
    assert by_id["core_simulator"].live_basenames == ("CoreSimulatorService", "simdiskimaged")
    assert by_id["claude_support"].label_ko == "앱 지원 데이터"
    assert by_id["rancher_desktop"].observe_basenames == ("Rancher Desktop", "rancher-desktop")
    assert by_id["rancher_desktop"].touch == "report_only"
    assert by_id["downloads"].kind == "user_data"
    assert by_id["app_bundle"].suffix == ".app"


def test_ollama_covers_models_not_backup():
    ident = identity_for("/Users/cskim/.ollama/models", ())
    assert ident == Identity("ollama_models", "model_store", "모델 저장소", "report_only")
    assert identity_for("/Users/cskim/.ollama-backup", ()).rule_id is None


def test_rsupport_descendant_is_user_data():
    ident = identity_for("/Users/cskim/Documents/rsupport/src", ())
    assert ident == Identity("rsupport_docs", "user_data", "사용자 데이터", "report_only")
    assert identity_for("/Users/cskim/Documents/rsupport-old", ()).rule_id is None


def test_simulator_live_only_for_named_processes():
    live = identity_for(
        "/Users/cskim/Library/Developer/CoreSimulator",
        ((222, "/usr/libexec/simdiskimaged"),),
    )
    idle = identity_for(
        "/Users/cskim/Library/Developer/CoreSimulator",
        ((1, "/sbin/launchd"),),
    )
    assert live.touch == "live"
    assert idle.touch == "report_only"


def test_claude_live_when_basename_matches():
    ident = identity_for(
        "/Users/cskim/Library/Application Support/Claude",
        ((9047, "/Applications/Claude.app/Contents/MacOS/Claude"),),
    )
    assert ident.touch == "live"
    assert ident.kind == "app_support"


def test_ollama_daemon_is_listed_without_changing_touch():
    processes = ((58323, "/usr/local/bin/ollama"),)
    assert identity_for("/Users/cskim/.ollama", processes).touch == "report_only"
    assert observed_daemons("/Users/cskim/.ollama", processes) == (
        "/usr/local/bin/ollama",
    )


def test_uv_cache_label_is_not_a_delete_flag():
    ident = identity_for("/Users/cskim/.cache/uv", ())
    assert ident == Identity("uv_cache", "cache", "패키지 캐시", "reinstallable")


def test_unknown_paths_stay_unknown():
    assert identity_for("/Users/cskim/.cache/codex-runtimes", ()).rule_id is None
    assert identity_for(
        "/Users/cskim/Library/Application Support/Google", ()
    ).rule_id is None


def test_cellar_false_match_is_not_reinstallable():
    ident = identity_for("/Users/cskim/Cellar", ())
    assert ident.rule_id == "homebrew_cellar"
    assert ident.touch == "report_only"


def test_remaining_rules_match_these_paths():
    cases = {
        "/Users/cskim/Downloads/a": "downloads",
        "/Users/cskim/.npm": "npm_cache",
        "/Users/cskim/.Trash": "trash",
        "/Users/cskim/.rustup": "rustup",
        "/Users/cskim/Library/Caches/Homebrew": "homebrew_cache",
        "/opt/homebrew/Cellar/llvm": "homebrew_cellar",
        "/Applications/Xcode.app": "app_bundle",
        "/Applications/Xcode.app/Contents": "app_bundle",
    }
    for path, rule_id in cases.items():
        assert identity_for(path, ()).rule_id == rule_id


def test_equal_suffix_length_uses_rule_id_order():
    assert identity_for("/Users/cskim/Downloads/.cache/uv", ()).rule_id == "downloads"


def test_observed_daemons_sort_by_comm():
    processes = (
        (9, "/usr/libexec/simdiskimaged"),
        (3, "/Library/Developer/PrivateFrameworks/CoreSimulator.framework/CoreSimulatorService"),
    )
    assert observed_daemons(
        "/Users/cskim/Library/Developer/CoreSimulator", processes
    ) == (
        "/Library/Developer/PrivateFrameworks/CoreSimulator.framework/CoreSimulatorService",
        "/usr/libexec/simdiskimaged",
    )
