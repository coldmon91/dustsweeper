# 큰 경로를 지우지 않고 확인하는 방법

이 문서는 용량이 큰 경로를 들어가 보고, 필요할 때 열린 파일과 종류를 확인하는 방법을 보여 준다.
파일을 지우거나 옮기지 않는다.

저장소 루트에서 `uv run dustsweeper`로 실행한다.
인자가 없으면 현재 디렉터리의 용량 탐색기다.
`dust`가 설치되어 있어야 측정이 된다.

## 큰 디렉터리 안으로 들어가기

터미널에서 현재 디렉터리의 큰 항목을 본다.

```bash
cd /Users/cskim/Documents/rsupport
uv run dustsweeper
```

다른 경로만 보려면 루트를 지정한다.

```bash
uv run dustsweeper browse --root "$HOME"
```

위아래 키로 고르고, Enter로 디렉터리에 들어가고, Backspace나 왼쪽 방향키로 올라온다.
q로 나간다.
`d` 다음 `y`는 선택한 항목을 휴지통으로 옮긴다. 다른 키는 취소다.
비우기 전에는 용량이 줄지 않는다.
화면 밖의 작은 항목은 `나머지 N개`로 접힌다.
이 화면은 크기와 비율만 보여 준다.
열린 파일과 종류가 필요하면 아래 JSON 경로를 쓴다.

## 홈에서 큰 경로만 고르기

1GiB 이상, 깊이 2, 최대 50개를 본다.

```bash
cd /Users/cskim/Documents/dustsweeper
uv run dustsweeper scan --root "$HOME" --root /Applications
```

표준출력은 JSON이다.
더 작은 기준이 필요하면 `--min-bytes`를 낮춘다.
기본값은 `--depth 2`, `--min-bytes 1073741824`, `--limit 50`이다.

결과를 파일로 남기려면 표준출력을 리다이렉트한다.

```bash
uv run dustsweeper scan --root "$HOME" > /tmp/scan.json
```

## 열린 파일과 정체를 붙이기

저장한 JSON에 열린 파일, 실행 중인 프로세스, 최근 사용일, 경로 규칙을 붙인다.
`lsof`가 한 번 돌므로 홈 전체는 시간이 걸릴 수 있다.

```bash
uv run dustsweeper inspect --report /tmp/scan.json > /tmp/inspect.json
```

`--report`와 `--root`는 같이 쓰지 않는다.
같이 쓰면 종료 코드 2이고, 표준에러는 `report and root are mutually exclusive`다.

`~/.ollama`는 열린 파일이 없어도 데몬이 실행 중일 수 있다.
`touch` 값은 정체 표시일 뿐, 삭제를 허가하지 않는다.

## 규칙이 못 붙인 경로만 설명받기

규칙이 붙은 카드는 외부 명령에 보내지 않는다.
설명 명령은 직접 지정한다. 기본 클라우드 주소는 없다.

```bash
DUSTSWEEPER_NARRATE_CMD='python3 tests/fixtures/fake_narrate.py' \
  uv run dustsweeper narrate --report /tmp/inspect.json
```

`DUSTSWEEPER_NARRATE_CMD`가 없으면 종료 코드 2이고, 표준에러는 `DUSTSWEEPER_NARRATE_CMD is unset`이다.
파일 내용은 읽지 않는다.

## 저장본 없이 바로 확인하기

측정과 증거 조회를 한 번에 하려면 `inspect`에 루트를 준다.
이미 만든 JSON이 있으면 위의 `--report` 경로를 쓴다.

```bash
uv run dustsweeper inspect --root "$HOME" --min-bytes 1073741824
```

## 예시 데이터로 동작만 확인하기

홈을 훑지 않고 명령이 도는지 보려면 저장소의 예시 파일을 쓴다.

```bash
uv run dustsweeper scan --dust-json tests/fixtures/dust-bytes.json --root /tmp/scan --min-bytes 100000 --limit 50 --depth 1
```

종료 코드 0이면 표준출력은 `keep` 경로와 크기 204800만 담은 JSON이다.

```bash
uv run dustsweeper inspect --report tests/fixtures/scan-two.json --lsof tests/fixtures/lsof-mixed.txt --ps tests/fixtures/ps-live.txt --mdls tests/fixtures/mdls-two.json
```

```bash
DUSTSWEEPER_NARRATE_CMD='python3 tests/fixtures/fake_narrate.py' uv run dustsweeper narrate --report tests/fixtures/cards-mixed.json
```

음수 `--depth`나 음수 `--min-bytes`는 종료 코드 2다.
`--dust-json`은 루트가 하나일 때만 쓴다.
