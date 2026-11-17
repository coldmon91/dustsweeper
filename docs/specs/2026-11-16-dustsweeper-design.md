# dustsweeper 설계 기록

이 문서는 2026-11-16 세션의 결정을 구현 계약으로 옮긴 것이다.
1차·2차·3차 번호는 그 세션에 없었다.
이 문서가 그 번호를 이렇게 고정한다.

- 1차 `scan`: `dust`로 측정하고 크기 기준 후보만 JSON으로 낸다.
- 2차 `inspect`: 후보에 `lsof`·`ps`·`mdls` 증거와 경로 규칙을 붙인다.
- 3차 `narrate`: 규칙이 못 붙인 카드만 한국어로 서술한다.

삭제는 1차·2차·3차 밖에 있다.
어느 명령도 파일을 영구 삭제하지 않는다.
휴지통 이동은 `docs/specs/2026-11-17-trash-design.md`만 허용한다.

## 목적

사용자는 용량이 아니라 지금 건드려도 되는지가 필요하다.
측정은 `dust`, 정체는 로컬 규칙, 열린 파일과 최근 사용일은 로컬 명령, 서술은 규칙이 못 붙인 카드에만 LLM이 맡는다.

## 하지 않는 일

- `rm`, `unlink`, 영구 삭제, 격리 디렉터리 이동
- 휴지통 이동은 `docs/specs/2026-11-17-trash-design.md`만 허용한다.
- 후보 파일의 내용 읽기
- 홈 트리 전체 또는 형제 경로를 모델에 보내기
- 기본 클라우드 LLM 엔드포인트, API 키 저장
- Linux, Windows, GUI, 예약 실행
- `git init`, 브랜치 생성

## 전역 제약

- 플랫폼은 macOS다. 관측한 `dust`는 1.2.6, `lsof`는 4.91이다.
- Dust 1.2.6의 `-j` 도움말은 "current directory"라고 적혀 있다. 관측 결과는 표준출력 JSON이고 표준에러는 비어 있다. 구현은 표준출력을 읽고, 디스크에 JSON 파일이 생겼는지 찾지 않는다.
- 크기 출력은 `-o b`일 때 `208896B`처럼 숫자와 접미사 `B`다. `4.0Ki` 같은 값은 오류다.
- 기본값: `min_bytes` `1073741824`, `depth` `2`, `limit` `50`, report `version` `1`.
- Python `>=3.12`. 패키지 이름은 `dustsweeper`. 의존성 추가는 `uv add`만 쓴다.
- `touch`는 `report_only`, `live`, `reinstallable`, `unknown` 중 하나다. 어느 값도 삭제 허가가 아니다.
- 열린 파일은 후보 경로와 같거나 그 하위일 때만 해당한다. 상위 경로는 해당하지 않는다.
- 앱 최근 사용일과 데몬 실행은 별개 필드다.
- `/Users/cskim/Documents/rsupport`로 끝나는 경로와 그 하위는 사용자 데이터다. 경로와 크기만 보고하고 내용은 읽지 않는다.

## dust 호출

인자 순서는 이 목록 그대로다.

`dust -j -o b -P -d <depth> -- <root>`

`-n`, `-z`, `-x`는 붙이지 않는다.
필터와 개수 제한은 파싱 뒤에 한다.
`--dust-json FILE`이 있으면 이 명령을 실행하지 않고 그 파일의 표준출력 대용 텍스트를 파싱한다.
이 플래그는 루트가 정확히 하나일 때만 허용한다.

크기 문법: `^[0-9]+B$`.
그 외는 `ScanError`이고 메시지는 `dust size is not bytes: <원문>`이다.

경로: `name`이 `.`이면 루트, 깊이 0이다.
`./keep`은 `<root>/keep`, 깊이 1이다.
`/`로 시작하면 그 절대 경로를 쓴다.
자식의 깊이는 부모 깊이 + 1이다.

후보 선택: 깊이 0을 빼고, `size_bytes < min_bytes`를 빼고, `(-size_bytes, path)` 순으로 정렬한 뒤 `limit`개만 남긴다.
여러 루트는 합친 다음 한 번만 `limit`을 적용한다.

## 리포트 공통

직렬화는 `json.dumps(..., ensure_ascii=False, indent=2, sort_keys=True)`와 끝의 개행 하나다.
키를 생략해서 null을 표현하지 않는다.
null이 계약이면 JSON `null`을 쓴다.

1차 본문 키: `candidates`, `min_bytes`, `version`.
후보 키: `depth`, `path`, `size_bytes`.

2차가 후보에 더하는 키: `evidence`, `identity`.
`evidence` 키: `daemon_commands`, `last_used`, `open_files`.
`open_files` 원소 키: `command`, `path`, `pid`.
`identity` 키: `kind`, `label_ko`, `rule_id`, `touch`.
맞지 않는 규칙은 `rule_id: null`, `kind: "unknown"`, `label_ko: ""`, `touch: "unknown"`.

3차가 카드에 더하는 키: `narration`.
맞는 규칙의 `narration`은 `null`.
불일치 카드의 `narration` 키: `source`, `text_ko`.
`source`는 `llm` 또는 `refused`다.

## 증거

한 번의 `lsof -F pcn` 텍스트를 모든 후보가 공유한다.
후보마다 `lsof +D`를 실행하지 않는다.
필드 첫 글자가 종류다. `p`는 PID, `c`는 명령, `n`은 경로다.
`f`는 `-F pcn`에도 나온다. `p`, `c`, `n`이 아닌 줄은 무시한다.
`n` 값이 `/`로 시작하지 않으면 무시한다. `n->0x...`는 경로가 아니다.
현재 `p`와 `c`가 `n`에 적용된다.

`ps -axo pid=,comm=`의 각 줄은 앞 공백을 지우고, 첫 공백에서 PID와 comm으로 나눈다.

`mdls -name kMDItemLastUsedDate -raw <path>`의 원문을 경로별로 받는다.
`2026-10-19 09:53:41 +0000`만 `2026-10-19T09:53:41Z`로 바꾼다.
`(null)`, 빈 문자열, 다른 오프셋, 파싱 실패는 `null`이다. 예외로 프로세스를 죽이지 않는다.
`mdls`가 개행 없이 `(null)`을 내는 것을 관측했다. 파서는 앞뒤 공백만 제거하고 개행을 요구하지 않는다.

## 경로 규칙

`path_matches(path, suffix)`:

- 끝의 `/`는 제거하고 비교한다.
- `suffix`가 `.`으로 시작하면, 경로 성분 중 하나가 그 접미사로 끝나면 맞다. `Xcode.app`과 `Xcode.app/Contents`는 `.app`에 맞다.
- 그 외에는 `suffix`가 경로 안에 있고, 바로 다음 문자가 끝이거나 `/`이면 맞다.
- `/.ollama`는 `/Users/cskim/.ollama`와 `/Users/cskim/.ollama/models`에 맞다.
- `/.ollama`는 `/Users/cskim/.ollama-backup`에 맞지 않는다.
- `/Documents/rsupport`는 `/Users/cskim/Documents/rsupport/src`에 맞다.
- `/Documents/rsupport`는 `/Users/cskim/Documents/rsupport-old`에 맞지 않는다.

여러 규칙이 맞으면 `suffix` 문자열이 가장 긴 규칙 하나다.
같은 길이의 두 규칙이 같은 경로에 맞으면 `rule_id` 오름차순으로 첫 규칙이다.

`live_basenames`의 basename이 실행 중이면 `touch`는 `live`다.
아니면 규칙의 기본 `touch`다.
`observe_basenames`와 `live_basenames`에 해당하는 comm은 `daemon_commands`에 넣는다.
정렬은 comm 오름차순, 같은 comm은 PID 오름차순이다.
같은 comm은 한 번만 남긴다.
규칙이 없으면 `daemon_commands`는 빈 목록이다. 경로 이름으로 프로세스를 추측하지 않는다.

basename은 comm의 마지막 `/` 성분이다. 비교는 대소문자를 구분한다.

| rule_id | suffix | kind | label_ko | touch | live_basenames | observe_basenames |
|---|---|---|---|---|---|---|
| ollama_models | `/.ollama` | model_store | 모델 저장소 | report_only |  | ollama |
| core_simulator | `/Library/Developer/CoreSimulator` | simulator | 시뮬레이터 이미지 | report_only | CoreSimulatorService, simdiskimaged | CoreSimulatorService, simdiskimaged |
| claude_support | `/Library/Application Support/Claude` | app_support | 앱 지원 데이터 | report_only | Claude | Claude |
| rancher_desktop | `/Library/Application Support/rancher-desktop` | app_support | 컨테이너 런타임 데이터 | report_only |  | Rancher Desktop, rancher-desktop |
| rsupport_docs | `/Documents/rsupport` | user_data | 사용자 데이터 | report_only |  |  |
| downloads | `/Downloads` | user_data | 사용자 데이터 | report_only |  |  |
| uv_cache | `/.cache/uv` | cache | 패키지 캐시 | reinstallable |  |  |
| npm_cache | `/.npm` | cache | 패키지 캐시 | reinstallable |  |  |
| trash | `/.Trash` | cache | 휴지통 | reinstallable |  |  |
| rustup | `/.rustup` | toolchain | 툴체인 | reinstallable |  |  |
| homebrew_cache | `/Library/Caches/Homebrew` | cache | 패키지 캐시 | reinstallable |  |  |
| homebrew_cellar | `/Cellar` | toolchain | 패키지 설치본 | report_only |  |  |
| app_bundle | `.app` | app_bundle | 앱 번들 | report_only |  |  |

`/Users/cskim/.cache/codex-runtimes`와 `/Users/cskim/Library/Application Support/Google`은 맞는 규칙이 없다.
`/Cellar`가 사용자 폴더에 잘못 맞으면 서술을 생략할 뿐, `reinstallable`이 되지 않는다.

## 서술

환경 변수 `DUSTSWEEPER_NARRATE_CMD`가 명령이다.
없으면 `narrate`는 종료 코드 2, 표준에러 `DUSTSWEEPER_NARRATE_CMD is unset`, 네트워크 호출 없음.
명령은 `shlex.split`으로 나누고, 표준입력으로 카드 JSON 하나를 받고, 표준출력으로 UTF-8 텍스트를 낸다.
제한 시간은 30초다. 상수 이름은 `NARRATE_TIMEOUT_SEC`이고 값은 `30`이다.
종료 코드가 0이 아니거나 시간이 넘으면 `source`는 `refused`, `text_ko`는 `서술을 거절함. 명령이 실패함.`이다.

표준입력 JSON 키는 `card`, `instruction`뿐이다.
`instruction`은 다음 한 줄이다.

`이 카드 하나만 한국어 한 단락으로 설명하라. 파일 내용은 주어지지 않았다. 삭제, rm, unlink, trash, 휴지통을 제안하지 마라. 사용 중이 아니라고 단정하지 마라.`

`card` 키는 `daemon_commands`, `last_used`, `open_commands`, `path`, `size_bytes`뿐이다.
`open_commands`는 그 카드의 `open_files[].command`를 순서대로 담는다.
다른 카드의 경로는 넣지 않는다.

수락: 거절 바늘이 없으면 `source`는 `llm`이고 `text_ko`는 명령 출력의 앞뒤 공백을 제거한 값이다.
거절 바늘: 라틴 문자열 `rm `, `unlink`, `trash`는 대소문자 무시. 한국어 `지워`, `지워도`, `삭제해`는 그대로.
`삭제 명령은 없다`는 수락이다.
`지워도 됩니다`와 `RM -rf /tmp`는 거절이다.
거절 문구는 `서술을 거절함. 삭제 지시가 포함되어 있음.`이다.

맞는 규칙의 카드는 명령에 넘기지 않는다.

## 명령

| 명령 | 하는 일 | 하지 않는 일 |
|---|---|---|
| `dustsweeper scan` | 1차 JSON | 증거, 규칙, 서술, 삭제 |
| `dustsweeper inspect` | 2차 JSON | 서술, 삭제, 후보 내용 읽기 |
| `dustsweeper narrate` | 3차 JSON | 다시 스캔, 삭제 |

인자가 없으면 탐색기다.
그 계약과 사용법 한 줄은 `docs/specs/2026-11-17-browse-tui-design.md`가 대체한다.

아래 세 줄은 각 차수가 끝나던 때의 사용법이다. 현재 사용법이 아니다.
- 1차만 있을 때: `usage: dustsweeper scan --root PATH [--depth N] [--min-bytes N] [--limit N] [--dust-json FILE]`
- 2차까지 있을 때: `usage: dustsweeper {scan|inspect}`
- 3차까지 있을 때: `usage: dustsweeper {scan|inspect|narrate}`

`delete`와 `rm` 하위 명령은 종료 코드 2다.
`scan`은 `--report`를 받지 않는다.
`inspect`에 `--report`와 `--root`를 함께 주면 종료 코드 2, 표준에러 `report and root are mutually exclusive`다.
`inspect`는 `--report FILE`만으로 동작할 수 있다. 이때 `dust`를 실행하지 않는다. `load_candidates`는 `min_bytes`로 후보를 다시 거르지 않는다.
`narrate`는 `--report FILE`이 필수다.

종료 코드는 성공 `0`, 사용법·입력 오류 `2`뿐이다.

## 파일 책임

| 파일 | 책임 | 생기는 차수 |
|---|---|---|
| `src/dustsweeper/model.py` | 상수, `Node`, `Candidate`, 이후 `Card` | 1차, 2차가 확장 |
| `src/dustsweeper/scan.py` | dust 인자, 파싱, 후보 선택 | 1차 |
| `src/dustsweeper/report.py` | JSON 직렬화와 역직렬화 | 1차, 2·3차가 확장 |
| `src/dustsweeper/cli.py` | 인자, 종료 코드 | 1차, 2·3차가 확장 |
| `src/dustsweeper/evidence.py` | lsof, ps, mdls, 열린 파일 대조 | 2차 |
| `src/dustsweeper/rules.py` | 규칙 표, 정체, 데몬 목록 | 2차 |
| `src/dustsweeper/narrate.py` | 서술 대상, 입력 JSON, 수락·거절 | 3차 |
| `README.md` | 현재 차수까지의 사용법 | 매 차수 |

## 계획

- 1차: `docs/plans/2026-11-16-phase1-scan.md`
- 2차: `docs/plans/2026-11-16-phase2-inspect.md`
- 3차: `docs/plans/2026-11-16-phase3-narrate.md`

2차는 1차의 `Candidate` JSON이 있어야 한다.
3차는 2차의 `Card` JSON이 있어야 한다.
각 계획은 그 명령만으로 검증 가능한 프로그램을 만든다.
