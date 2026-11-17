# 3차 narrate 구현 계획

> **For agentic workers:** Implement this plan task-by-task, in order. Steps use checkbox (`- [ ]`) syntax for tracking — mark each one done as you finish it.

**Goal:** 규칙이 못 붙인 카드만 외부 명령으로 한국어 서술하고, 삭제 지시가 있으면 그 서술을 거절한다.

**Architecture:** `narrate`는 2차 JSON을 읽고 불일치 카드만 `DUSTSWEEPER_NARRATE_CMD`의 표준입력으로 보낸다. 기본 클라우드 엔드포인트는 없다. 맞는 규칙의 `narration`은 `null`이다.

**Tech Stack:** Python >=3.12, uv, ruff, ty, pytest. 표준 라이브러리 `shlex`만 추가 사용한다. 새 패키지는 추가하지 않는다.

**Spec:** `docs/specs/2026-11-16-dustsweeper-design.md`

## Global Constraints

- 플랫폼은 macOS다. 관측한 `dust`는 1.2.6, `lsof`는 4.91이다.
- Dust 1.2.6의 `-j` 도움말은 "current directory"라고 적혀 있다. 관측 결과는 표준출력 JSON이고 표준에러는 비어 있다. 이 계획은 `dust`를 호출하지 않는다.
- 크기 출력은 `-o b`일 때 `208896B`처럼 숫자와 접미사 `B`다. `4.0Ki` 같은 값은 오류다.
- 기본값: `min_bytes` `1073741824`, `depth` `2`, `limit` `50`, report `version` `1`.
- Python `>=3.12`. 패키지 이름은 `dustsweeper`. 의존성 추가는 `uv add`만 쓴다. 3차는 `uv add`를 호출하지 않는다.
- `touch`는 `report_only`, `live`, `reinstallable`, `unknown` 중 하나다. 어느 값도 삭제 허가가 아니다.
- 열린 파일은 후보 경로와 같거나 그 하위일 때만 해당한다. 3차는 이 대조를 다시 하지 않고 2차 JSON을 믿는다.
- 앱 최근 사용일과 데몬 실행은 별개 필드다. 둘 다 `card`에 따로 넣는다.
- `/Users/cskim/Documents/rsupport`로 끝나는 경로와 그 하위는 사용자 데이터다. 규칙이 맞으므로 서술 명령에 넘기지 않는다.
- 소스, README, 프롬프트에 `os.remove`, `os.unlink`, `shutil.rmtree`, `send2trash`를 두지 않는다.
- `git init`과 브랜치 생성은 하지 않는다.
- LLM 입력은 그 카드의 `path`, `size_bytes`, `open_commands`, `daemon_commands`, `last_used`뿐이다. 파일 바이트, 형제 경로, 전체 트리는 보내지 않는다.

## 파일 지도

- `src/dustsweeper/narrate.py`: 대상 필터, 표준입력 JSON, 수락·거절, 명령 실행 경계.
- `src/dustsweeper/report.py`: `load_cards`, 3차 직렬화.
- `src/dustsweeper/cli.py`: `narrate` 분기.
- `tests/test_narrate.py`, `tests/test_cli.py`
- `tests/fixtures/cards-mixed.json`, `tests/fixtures/fake_narrate.py`
- `README.md`: `narrate` 절.

2차 타입을 이 계획에서 다시 정의하지 않는다. 구현자는 2차가 만든 아래 시그니처를 쓴다.

```python
OpenFile(pid: int, command: str, path: str)
Evidence(open_files: tuple[OpenFile, ...], daemon_commands: tuple[str, ...], last_used: str | None)
Identity(rule_id: str | None, kind: str, label_ko: str, touch: str)
Card(path: str, size_bytes: int, depth: int, evidence: Evidence, identity: Identity)
```

---

### Task 1: 서술 대상과 입력 JSON

**Files:**
- Create: `src/dustsweeper/narrate.py`
- Create: `tests/test_narrate.py`

**Interfaces:**
- Consumes: 2차 `Card`, `Evidence`, `Identity`, `OpenFile`
- Produces: `NARRATE_INSTRUCTION: str` 스펙의 한 줄
- Produces: `cards_for_narration(cards: tuple[Card, ...]) -> tuple[Card, ...]`
- Produces: `narration_stdin(card: Card) -> str`

- [x] **Step 1: State the invariants and test assertions**

**Invariants:** `rule_id`가 `None`인 카드만 대상이다. 표준입력 최상위 키는 `card`와 `instruction`뿐이다. `card` 키는 `daemon_commands`, `last_used`, `open_commands`, `path`, `size_bytes`뿐이다. `open_commands`는 `open_files`의 `command` 순서다. 직렬화는 `sort_keys=True`, `ensure_ascii=False`, `indent=2`, 끝 개행이다. 다른 카드의 경로는 문자열에 없다.

**Test assertions:** `tests/test_narrate.py`

```python
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
```

- [x] **Step 2: Implement until the assertions hold**

필터와 표준입력 생성만 구현한다. 프로세스 실행은 다음 태스크다.

- [x] **Step 3: Verify**

Run: `uv run pytest tests/test_narrate.py -q`
Expected: `2 passed`

---

### Task 2: 서술 수락과 거절

**Files:**
- Modify: `src/dustsweeper/narrate.py`
- Modify: `tests/test_narrate.py`

**Interfaces:**
- Consumes: Task 1의 `narration_stdin`, `cards_for_narration`
- Produces: `Narration(path: str, text_ko: str, source: str)` frozen dataclass
- Produces: `REFUSAL_DELETE = "서술을 거절함. 삭제 지시가 포함되어 있음."`
- Produces: `REFUSAL_FAILED = "서술을 거절함. 명령이 실패함."`
- Produces: `NARRATE_TIMEOUT_SEC = 30`
- Produces: `class NarrateError(Exception)`
- Produces: `accept_narration(path: str, text: str) -> Narration`
- Produces: `narrate_card(card: Card, runner: Callable[[str], str]) -> Narration`

- [x] **Step 1: State the invariants and test assertions**

**Invariants:** 라틴 바늘 `rm `, `unlink`, `trash`는 대소문자를 무시한다. 한국어 바늘 `지워`, `지워도`, `삭제해`는 그대로다. `삭제 명령은 없다`는 수락이다. `runner`가 `NarrateError`를 일으키면 `REFUSAL_FAILED`다. 시간 초과도 `NarrateError`로 들어와 같은 문구가 된다. 실제 30초 대기는 테스트에 넣지 않는다.

**Test assertions:** `tests/test_narrate.py`

```python
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
```

- [x] **Step 2: Implement until the assertions hold**

`accept_narration`과 `narrate_card`를 단언이 통과할 때까지 구현한다. `narrate_card`는 `cards_for_narration`에 없는 카드를 받아도 명령 runner를 호출하기 전에 `NarrateError`를 일으킨다. 그 단언을 같은 파일에 추가한다.

```python
def test_narrate_card_rejects_matched_card():
    matched = Card(
        "/Users/cskim/.ollama", 10, 1, Evidence((), (), None),
        Identity("ollama_models", "model_store", "모델 저장소", "report_only"),
    )

    def runner(stdin: str) -> str:
        raise AssertionError("sent")

    with pytest.raises(NarrateError):
        narrate_card(matched, runner)
```

- [x] **Step 3: Verify**

Run: `uv run pytest tests/test_narrate.py -q`
Expected: `8 passed`

---

### Task 3: narrate 명령

**Files:**
- Modify: `src/dustsweeper/report.py`
- Modify: `src/dustsweeper/cli.py`
- Modify: `tests/test_cli.py`
- Create: `tests/fixtures/cards-mixed.json`
- Create: `tests/fixtures/fake_narrate.py`
- Create: `tests/fixtures/fake_refuse.py`

**Interfaces:**
- Consumes: `cards_for_narration`, `narration_stdin`, `accept_narration`, `narrate_card`, `NARRATE_TIMEOUT_SEC`
- Produces: `load_cards(raw: str) -> tuple[Card, ...]`
- Produces: `render_narrated(cards: tuple[Card, ...], narrations: dict[str, Narration], min_bytes: int) -> str`
- Produces: `main`의 `narrate --report FILE`

- [x] **Step 1: State the invariants and test assertions**

**Invariants:** `DUSTSWEEPER_NARRATE_CMD`가 없으면 종료 코드 2, 표준에러 `DUSTSWEEPER_NARRATE_CMD is unset`, 표준출력은 비어 있다. 네트워크 클라이언트 코드는 `src/`에 없다. 맞는 카드의 `narration`은 JSON `null`이다. 불일치 카드만 명령의 표준입력으로 간다. 인자 없음의 사용법은 `usage: dustsweeper {scan|inspect|narrate}`다. 1차 `scan` 출력과 2차 `inspect` 출력 단언은 유지한다. `scan`과 `inspect`는 이 명령을 호출하지 않는다.

**Test assertions:** `tests/test_cli.py`의 사용법 기대를 다음으로 바꾼다.

```python
assert capsys.readouterr().err == "usage: dustsweeper {scan|inspect|narrate}\n"
```

```python
def test_narrate_without_command(monkeypatch, capsys):
    monkeypatch.delenv("DUSTSWEEPER_NARRATE_CMD", raising=False)
    code = main(["narrate", "--report", "tests/fixtures/cards-mixed.json"])
    captured = capsys.readouterr()
    assert code == 2
    assert captured.out == ""
    assert captured.err == "DUSTSWEEPER_NARRATE_CMD is unset\n"

def test_narrate_sends_only_unknown(monkeypatch, capsys, tmp_path):
    captured = tmp_path / "stdin.json"
    monkeypatch.setenv("DUSTSWEEPER_NARRATE_CMD", "python3 tests/fixtures/fake_narrate.py")
    monkeypatch.setenv("FAKE_STDIN_PATH", str(captured))
    code = main(["narrate", "--report", "tests/fixtures/cards-mixed.json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    by_path = {item["path"]: item for item in payload["candidates"]}
    assert by_path["/Users/cskim/.ollama"]["narration"] is None
    assert by_path["/Users/cskim/.cache/codex-runtimes"]["narration"] == {
        "source": "llm",
        "text_ko": "정체를 규칙으로 확정하지 못했다.",
    }
    assert "/Users/cskim/.ollama" not in captured.read_text()

def test_narrate_refuses_delete_advice(monkeypatch, capsys):
    monkeypatch.setenv("DUSTSWEEPER_NARRATE_CMD", "python3 tests/fixtures/fake_refuse.py")
    code = main(["narrate", "--report", "tests/fixtures/cards-mixed.json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    unknown = next(
        item for item in payload["candidates"]
        if item["path"] == "/Users/cskim/.cache/codex-runtimes"
    )
    assert unknown["narration"]["source"] == "refused"
    assert unknown["narration"]["text_ko"] == "서술을 거절함. 삭제 지시가 포함되어 있음."

def test_src_has_no_network_client():
    text = "\n".join(path.read_text() for path in Path("src").rglob("*.py"))
    for token in ("urllib.request", "httpx", "openai", "socket.create_connection"):
        assert token not in text
```

`tests/fixtures/cards-mixed.json`의 내용은 다음이다.

```json
{
  "candidates": [
    {
      "depth": 1,
      "evidence": {
        "daemon_commands": ["/usr/local/bin/ollama"],
        "last_used": "2026-10-19T09:53:41Z",
        "open_files": []
      },
      "identity": {
        "kind": "model_store",
        "label_ko": "모델 저장소",
        "rule_id": "ollama_models",
        "touch": "report_only"
      },
      "path": "/Users/cskim/.ollama",
      "size_bytes": 13958643712
    },
    {
      "depth": 2,
      "evidence": {
        "daemon_commands": [],
        "last_used": null,
        "open_files": []
      },
      "identity": {
        "kind": "unknown",
        "label_ko": "",
        "rule_id": null,
        "touch": "unknown"
      },
      "path": "/Users/cskim/.cache/codex-runtimes",
      "size_bytes": 5500000000
    }
  ],
  "min_bytes": 1073741824,
  "version": 1
}
```

`tests/fixtures/fake_narrate.py`의 내용은 다음이다. `FAKE_STDIN_PATH`가 없으면 파일을 만들지 않는다.

```python
import os
import sys
from pathlib import Path

raw = sys.stdin.read()
dest = os.environ.get("FAKE_STDIN_PATH")
if dest:
    Path(dest).write_text(raw)
sys.stdout.write("정체를 규칙으로 확정하지 못했다.\n")
```

`tests/fixtures/fake_refuse.py`의 내용은 다음이다.

```python
import sys

sys.stdout.write("지워도 됩니다\n")
```

두 스크립트는 네트워크를 열지 않는다. 제품 코드는 `FAKE_STDIN_PATH`를 읽지 않는다.

- [x] **Step 2: Implement until the assertions hold**

`narrate`는 환경 변수를 `shlex.split`으로 나누고, 불일치 카드마다 표준입력으로 `narration_stdin`을 넘긴다. 제한 시간은 `NARRATE_TIMEOUT_SEC`다. 맞는 카드에는 명령을 실행하지 않는다. `render_narrated`는 2차 키를 유지하고 `narration`만 더한다.

- [x] **Step 3: Verify**

Run: `DUSTSWEEPER_NARRATE_CMD='python3 tests/fixtures/fake_narrate.py' uv run dustsweeper narrate --report tests/fixtures/cards-mixed.json`
Expected: 종료 코드 0. `.ollama`의 `narration`은 `null`. `codex-runtimes`의 `source`는 `llm`이고 `text_ko`는 `정체를 규칙으로 확정하지 못했다.`

Run: `uv run pytest -q`
Expected: `2차 35개 + 서술 8개 + narrate CLI 4개 = 47 passed`

Run: `uv run ruff check src tests && uv run ty check src`
Expected: 종료 코드 0

Run: `rg -n 'urllib.request|httpx|openai' src`
Expected: 일치 없음, 종료 코드 1

---

### Task 4: narrate 사용 설명

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: Task 3의 환경 변수와 종료 코드
- Produces: README `## narrate` 절

- [x] **Step 1: State the invariants and test assertions**

**Invariants:** `scan`과 `inspect` 절은 유지한다. `narrate` 절은 `DUSTSWEEPER_NARRATE_CMD`가 없을 때의 종료 코드 2와 표준에러 문장을 적는다. API 키, 기본 URL, 삭제 절차는 적지 않는다. 맞는 규칙은 모델에 보내지 않는다고 한 줄 적는다.

**Test assertions:** Step 3의 `rg`가 단언이다.

- [x] **Step 2: Implement until the assertions hold**

`## narrate`에 위 verify 명령 한 줄과, 명령이 없는 경우의 표준에러 문장을 적는다.

- [x] **Step 3: Verify**

Run: `rg -n 'DUSTSWEEPER_NARRATE_CMD is unset' README.md`
Expected: 일치 1줄

Run: `rg -n 'sk-|api.openai.com|os.remove' README.md`
Expected: 일치 없음, 종료 코드 1

Run: `uv run pytest -q`
Expected: `47 passed`
