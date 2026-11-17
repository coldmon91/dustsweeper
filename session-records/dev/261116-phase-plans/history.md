# phase-plans history

## 2026-11-16
- Context: `session-records/mac/261116-dust-cleanup-scan`는 dust+LLM 삭제 스크립트를 거절하고, 측정·규칙·서술로 나누라고 적혀 있다. 1·2·3차 번호는 그 기록에 없었다
- Decision: 1차는 `scan`, 2차는 `inspect`, 3차는 `narrate`. 삭제는 세 계획 모두 밖
- Decision: 구현 언어는 Python >=3.12, uv. 직전 요청이 리포트 스크립트였고 저장소에 Rust 경계가 없다
- Finding: Dust 1.2.6의 `-j` 도움말은 JSON을 현재 디렉터리에 쓴다고 하지만, 관측은 표준출력 JSON이고 표준에러는 비었다. `-o b` 크기는 `208896B` 형태의 문자열이다
- Finding: `mdls -raw`의 없는 속성은 개행 없는 `(null)`이다. `lsof -F pcn`은 `f` 줄도 내고, `n->0x...`는 경로가 아니다
- Decision: 열린 파일은 후보와 같거나 하위일 때만 해당한다. `~/.ollama`의 상위 `cwd`는 해당하지 않는다
- Output: `docs/specs/2026-11-16-dustsweeper-design.md`
- Output: `docs/plans/2026-11-16-phase1-scan.md`
- Output: `docs/plans/2026-11-16-phase2-inspect.md`
- Output: `docs/plans/2026-11-16-phase3-narrate.md`
- Decision: 커밋은 하지 않음. 이 디렉터리는 git 저장소가 아니고, 스펙·계획에 `/Users/cskim` 경로와 앱 데이터 위치가 있다

- Progress: 1차 Task 1 완료. `uv init --vcs none`으로 패키지를 만들었고 `.git`은 없다. `dustsweeper` 무인자 실행은 종료 코드 2, 사용법 한 줄. `pytest tests/test_cli.py`는 3 passed
- Next: Task 2 전에 검토를 기다린다

- Progress: 1·2·3차 태스크를 이 세션에서 순서대로 구현. `uv run pytest -q`는 47 passed. ruff와 ty는 통과
- Decision: 삭제는 구현하지 않음. narrate는 `DUSTSWEEPER_NARRATE_CMD`가 있을 때만 불일치 카드를 외부 명령에 보냄

- Progress: README를 큰 경로 확인 절차로 다시 씀. 삭제 절차와 클라우드 주소는 넣지 않음
