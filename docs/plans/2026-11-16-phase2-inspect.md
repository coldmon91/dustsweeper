# 2차 inspect 구현 계획

> **For agentic workers:** Implement this plan task-by-task, in order. Steps use checkbox (`- [ ]`) syntax for tracking — mark each one done as you finish it.

**Goal:** 1차 후보에 열린 파일, 데몬, 최근 사용일, 경로 규칙을 붙인 JSON을 낸다.

**Architecture:** `lsof -F pcn`과 `ps`는 후보 전체의 스냅샷 하나다. 후보마다 `lsof +D`를 돌리지 않는다. 정체는 스펙의 규칙 표만 붙이고, 맞지 않으면 `unknown`이다. 서술은 하지 않는다.

**Tech Stack:** Python >=3.12, uv, ruff, ty, pytest. 1차 패키지가 이미 있다.

**Spec:** `docs/specs/2026-11-16-dustsweeper-design.md`

## Global Constraints

- 플랫폼은 macOS다. 관측한 `dust`는 1.2.6, `lsof`는 4.91이다.
- Dust 1.2.6의 `-j` 도움말은 "current directory"라고 적혀 있다. 관측 결과는 표준출력 JSON이고 표준에러는 비어 있다. 이 계획은 `dust`를 다시 정의하지 않는다.
- 크기 출력은 `-o b`일 때 `208896B`처럼 숫자와 접미사 `B`다. `4.0Ki` 같은 값은 오류다.
- 기본값: `min_bytes` `1073741824`, `depth` `2`, `limit` `50`, report `version` `1`.
- Python `>=3.12`. 패키지 이름은 `dustsweeper`. 의존성 추가는 `uv add`만 쓴다. 2차는 새 의존성이 필요 없다.
- `touch`는 `report_only`, `live`, `reinstallable`, `unknown` 중 하나다. 어느 값도 삭제 허가가 아니다.
- 열린 파일은 후보 경로와 같거나 그 하위일 때만 해당한다. 상위 경로는 해당하지 않는다.
- 앱 최근 사용일과 데몬 실행은 별개 필드다.
- `/Users/cskim/Documents/rsupport`로 끝나는 경로와 그 하위는 사용자 데이터다. 경로와 크기만 보고하고 내용은 읽지 않는다.
- 소스, README, 프롬프트에 `os.remove`, `os.unlink`, `shutil.rmtree`, `send2trash`를 두지 않는다.
- `git init`과 브랜치 생성은 하지 않는다.
- 규칙 표, 접미사 대조, 날짜 형식, 거절 문구는 스펙의 표를 그대로 쓴다. 규칙을 추가하지 않는다.

## 파일 지도

- `src/dustsweeper/model.py`: `OpenFile`, `Evidence`, `Identity`, `Card`, `Rule`을 추가한다. 1차 타입은 유지한다.
- `src/dustsweeper/evidence.py`: lsof, ps, mdls 파싱과 열린 파일 대조.
- `src/dustsweeper/rules.py`: 규칙 표, `path_matches`, `identity_for`, `observed_daemons`.
- `src/dustsweeper/report.py`: 카드 JSON. 1차 `render_scan`은 유지한다.
- `src/dustsweeper/cli.py`: `inspect` 분기. 1차 `scan`은 유지한다.
- `tests/test_evidence.py`, `tests/test_rules.py`, `tests/test_cli.py`
- `tests/fixtures/scan-two.json`, `tests/fixtures/lsof-mixed.txt`, `tests/fixtures/ps-live.txt`, `tests/fixtures/mdls-two.json`
- `README.md`: `inspect` 절을 추가한다.

---

### Task 1: lsof, ps, mdls 파서

**Files:**
- Modify: `src/dustsweeper/model.py`
- Create: `src/dustsweeper/evidence.py`
- Create: `tests/test_evidence.py`
- Create: `tests/fixtures/lsof-mixed.txt`
- Create: `tests/fixtures/ps-live.txt`

**Interfaces:**
- Consumes: 1차 `Candidate(path: str, size_bytes: int, depth: int)`
- Produces: `OpenFile(pid: int, command: str, path: str)` frozen dataclass
- Produces: `parse_lsof(text: str) -> tuple[OpenFile, ...]`
- Produces: `open_files_for(candidate_path: str, opened: tuple[OpenFile, ...]) -> tuple[OpenFile, ...]`
- Produces: `parse_ps(text: str) -> tuple[tuple[int, str], ...]`
- Produces: `parse_last_used(mdls_raw: str) -> str | None`

- [x] **Step 1: State the invariants and test assertions**

**Invariants:** `lsof +D`는 호출하지 않는다. `n`이 `/`로 시작하지 않으면 버린다. 열린 파일 경로는 후보와 같거나 후보 + `/`로 시작할 때만 맞다. `parse_last_used`는 `YYYY-MM-DD HH:MM:SS +0000`만 ISO UTC로 바꾸고, 그 외는 `None`이다. 개행이 없어도 된다.

**Test assertions:** `tests/test_evidence.py`

```python
def test_ancestor_open_is_not_a_hit():
    text = "p58323\ncollama\nfcwd\nn/Users/cskim\nftxt\nn/usr/local/bin/ollama\n"
    opened = parse_lsof(text)
    assert open_files_for("/Users/cskim/.ollama", opened) == ()

def test_descendant_open_is_a_hit():
    text = (
        "p9047\ncClaude\nftxt\n"
        "n/Users/cskim/Library/Application Support/Claude/Local Storage/leveldb/LOCK\n"
    )
    opened = parse_lsof(text)
    assert open_files_for(
        "/Users/cskim/Library/Application Support/Claude", opened
    ) == (
        OpenFile(
            pid=9047,
            command="Claude",
            path="/Users/cskim/Library/Application Support/Claude/Local Storage/leveldb/LOCK",
        ),
    )

def test_ignores_non_path_names():
    assert parse_lsof("p1\ncx\nf1\nn->0xab\n") == ()

def test_parse_ps_strips_padding():
    assert parse_ps("  58323 /usr/local/bin/ollama\n") == (
        (58323, "/usr/local/bin/ollama"),
    )

def test_parse_last_used_utc_and_null():
    assert parse_last_used("2026-10-19 09:53:41 +0000") == "2026-10-19T09:53:41Z"
    assert parse_last_used("(null)") is None
    assert parse_last_used("") is None
    assert parse_last_used("2026-10-19 09:53:41 +0900") is None
```

`tests/fixtures/lsof-mixed.txt` 내용:

```
p58323
collama
fcwd
n/Users/cskim
ftxt
n/usr/local/bin/ollama
p9047
cClaude
ftxt
n/Users/cskim/Library/Application Support/Claude/Local Storage/leveldb/LOCK
```

`tests/fixtures/ps-live.txt` 내용:

```
58323 /usr/local/bin/ollama
9047 /Applications/Claude.app/Contents/MacOS/Claude
222 /usr/libexec/simdiskimaged
```

- [x] **Step 2: Implement until the assertions hold**

파서만 구현한다. 규칙과 CLI는 이 태스크에 넣지 않는다.

- [x] **Step 3: Verify**

Run: `uv run pytest tests/test_evidence.py -q`
Expected: `5 passed`

---

### Task 2: 규칙 표와 정체

**Files:**
- Modify: `src/dustsweeper/model.py`
- Create: `src/dustsweeper/rules.py`
- Create: `tests/test_rules.py`

**Interfaces:**
- Consumes: Task 1의 `parse_ps`가 내는 `tuple[tuple[int, str], ...]`
- Produces: `Rule(rule_id: str, suffix: str, kind: str, label_ko: str, touch: str, live_basenames: tuple[str, ...], observe_basenames: tuple[str, ...])`
- Produces: `RULES: tuple[Rule, ...]` 스펙 표 13행
- Produces: `Identity(rule_id: str | None, kind: str, label_ko: str, touch: str)`
- Produces: `path_matches(path: str, suffix: str) -> bool`
- Produces: `identity_for(path: str, processes: tuple[tuple[int, str], ...]) -> Identity`
- Produces: `observed_daemons(path: str, processes: tuple[tuple[int, str], ...]) -> tuple[str, ...]`

- [x] **Step 1: State the invariants and test assertions**

**Invariants:** `RULES`는 스펙 표와 같은 13개다. 가장 긴 `suffix`가 이긴다. 실행 중인 `live_basenames`가 있으면 `touch`는 `live`이고, 없으면 표의 기본값이다. `ollama` 프로세스는 `touch`를 바꾸지 않는다. 규칙이 없으면 `rule_id`는 `None`, `kind`는 `unknown`, `label_ko`는 `""`, `touch`는 `unknown`, `observed_daemons`는 `()`다. `reinstallable`이어도 삭제 API는 없다.

**Test assertions:** `tests/test_rules.py`

```python
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
```

- [x] **Step 2: Implement until the assertions hold**

스펙 표를 `RULES`에 옮기고 단언이 통과할 때까지 대조 함수를 구현한다. 표에 없는 경로 규칙을 추가하지 않는다.

- [x] **Step 3: Verify**

Run: `uv run pytest tests/test_rules.py -q`
Expected: `12 passed`

---

### Task 3: inspect 명령

**Files:**
- Modify: `src/dustsweeper/model.py`
- Modify: `src/dustsweeper/report.py`
- Modify: `src/dustsweeper/cli.py`
- Modify: `tests/test_cli.py`
- Create: `tests/fixtures/scan-two.json`
- Create: `tests/fixtures/mdls-two.json`

**Interfaces:**
- Consumes: `OpenFile`, `parse_lsof`, `open_files_for`, `parse_ps`, `parse_last_used`, `identity_for`, `observed_daemons`
- Produces: `Evidence(open_files: tuple[OpenFile, ...], daemon_commands: tuple[str, ...], last_used: str | None)`
- Produces: `Card(path: str, size_bytes: int, depth: int, evidence: Evidence, identity: Identity)`
- Produces: `build_cards(candidates: tuple[Candidate, ...], lsof_text: str, ps_text: str, mdls_by_path: dict[str, str]) -> tuple[Card, ...]`
- Produces: `render_cards(cards: tuple[Card, ...], min_bytes: int) -> str`
- Produces: `load_candidates(raw: str) -> tuple[Candidate, ...]`
- Produces: `main`의 `inspect --report FILE [--lsof FILE] [--ps FILE] [--mdls FILE]`

- [x] **Step 1: State the invariants and test assertions**

**Invariants:** `build_cards`는 후보 파일 바이트를 읽지 않는다. `load_candidates`는 `min_bytes`로 다시 거르지 않는다. `mdls_by_path`에 없는 경로의 `last_used`는 `None`이다. `inspect --report`는 `dust`를 실행하지 않는다. `--report`와 `--root`를 함께 주면 종료 코드 2다. 인자 없음의 사용법 줄은 `usage: dustsweeper {scan|inspect}`로 바뀐다. 1차 `scan` 표준출력 단언은 유지한다. 리포트에 `narration` 키는 없다.

**Test assertions:** `tests/test_cli.py`에 추가한다. 1차 `test_usage_line`의 기대 문자열은 다음으로 바꾼다.

```python
assert capsys.readouterr().err == "usage: dustsweeper {scan|inspect}\n"
```

```python
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
    code = main([
        "inspect",
        "--report", "tests/fixtures/scan-two.json",
        "--lsof", "tests/fixtures/lsof-mixed.txt",
        "--ps", "tests/fixtures/ps-live.txt",
        "--mdls", "tests/fixtures/mdls-two.json",
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == 1
    assert "narration" not in payload["candidates"][0]
    assert payload["candidates"][0]["identity"]["rule_id"] == "ollama_models"
    assert payload["candidates"][1]["identity"]["touch"] == "live"

def test_report_and_root_are_exclusive(capsys):
    code = main(["inspect", "--report", "tests/fixtures/scan-two.json", "--root", "/tmp"])
    assert code == 2
    assert capsys.readouterr().err == "report and root are mutually exclusive\n"
```

`tests/fixtures/scan-two.json`:

```json
{
  "candidates": [
    {
      "depth": 1,
      "path": "/Users/cskim/.ollama",
      "size_bytes": 13958643712
    },
    {
      "depth": 2,
      "path": "/Users/cskim/Library/Developer/CoreSimulator",
      "size_bytes": 17
    }
  ],
  "min_bytes": 1073741824,
  "version": 1
}
```

`tests/fixtures/mdls-two.json`:

```json
{"/Users/cskim/.ollama": "2026-10-19 09:53:41 +0000"}
```

- [x] **Step 2: Implement until the assertions hold**

`build_cards`는 이미 읽힌 문자열만 받는다. `inspect`의 `--lsof`, `--ps`, `--mdls`가 없으면 각각 `lsof -F pcn`, `ps -axo pid=,comm=`, 후보별 `mdls -name kMDItemLastUsedDate -raw`를 실행한다. 그 실행 경로는 fixture 테스트가 타지 않는다. 후보 파일을 `read_text`하거나 `read_bytes`하지 않는다.

- [x] **Step 3: Verify**

Run: `uv run dustsweeper inspect --report tests/fixtures/scan-two.json --lsof tests/fixtures/lsof-mixed.txt --ps tests/fixtures/ps-live.txt --mdls tests/fixtures/mdls-two.json`
Expected: 종료 코드 0. 첫 후보 `identity.rule_id`는 `ollama_models`, 둘째 후보 `identity.touch`는 `live`. 출력에 `narration`이 없다.

Run: `uv run pytest -q`
Expected: `1차 15개 + 증거 5개 + 규칙 12개 + inspect 3개 = 35 passed`

Run: `uv run ruff check src tests && uv run ty check src`
Expected: 종료 코드 0

---

### Task 4: inspect 사용 설명

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 3의 `inspect` 플래그
- Produces: README `## inspect` 절

- [x] **Step 1: State the invariants and test assertions**

**Invariants:** `scan` 절은 유지한다. `inspect` 절은 `--report`, `--lsof`, `--ps`, `--mdls`를 적는다. `narrate`는 적지 않는다. `touch` 값 설명이 삭제를 허가한다고 쓰지 않는다. `lsof +D`를 권하지 않는다.

**Test assertions:** Step 3의 `rg`가 단언이다.

- [x] **Step 2: Implement until the assertions hold**

`## inspect`에 fixture 명령 한 줄과, 열린 파일 없음과 데몬 실행이 동시에 참일 수 있다는 한 줄을 적는다. 예시는 `~/.ollama`다.

- [x] **Step 3: Verify**

Run: `rg -n 'dustsweeper inspect --report tests/fixtures/scan-two.json' README.md`
Expected: 일치 1줄

Run: `rg -n 'narrate|lsof \+D|os.remove' README.md`
Expected: 일치 없음, 종료 코드 1

Run: `uv run pytest -q`
Expected: `35 passed`
