# dust-cleanup-scan history

## 2026-11-16
- State: `/System/Volumes/Data` 460Gi 중 319Gi 사용, 116Gi 여유, 74% (`df -h`)
- Finding: `dust -d 1 ~` 합계 262Gi. Library 98Gi, Documents 74Gi, `.cache` 22Gi, `.ollama` 13Gi, `.rustup` 6.1Gi, `.npm` 5.7Gi, Downloads 5.5Gi, `.Trash` 5.3Gi
- Finding: `dust -d 2 ~/Library`. Application Support/rancher-desktop 17Gi, Claude 12Gi, Google 7.9Gi. Developer/CoreSimulator 17Gi. Caches 14Gi (Aside 3.4Gi, Google 2.4Gi, Homebrew 2.0Gi)
- Finding: `dust -d 1 ~/Documents`. rsupport 64Gi, Documents/.ollama 8.9Gi. 업무 트리로 보고 삭제 후보에서 제외
- Finding: `dust -d 1 ~/.cache`. uv 15Gi, codex-runtimes 5.5Gi
- Finding: `dust -d 1 /Applications`. 합계 19Gi. 최대는 Xcode.app 3.9Gi. 개별 앱은 캐시·모델보다 작음
- Finding: Homebrew Cellar 큰 항목 llvm@22 1.5Gi, mingw-w64 1.4Gi, musl-cross 928Mi, tesseract-lang 654Mi (`du -sh`)
- Decision: dust+LLM이 삭제 명령을 고르는 스크립트는 거절. dust는 측정, 분류는 규칙, LLM은 불확실 항목 설명만. 이유는 최대 항목이 업무 데이터·VM·모델이라 오판 시 복구 불가
- Finding: ollama PID 58323이 떠 있지만 `lsof +D ~/.ollama` 는 0줄. 열린 파일은 `/Applications/Ollama.app` 바이너리뿐 (`lsof -c ollama`). 모델 13Gi는 프로세스 소유와 현재 개방이 다름
- Finding: `mdls` Ollama.app 최근 사용 2026-10-19. 실행 중인 바이너리는 `/usr/local/bin/ollama`. 앱 최근 사용일과 데몬 실행은 별개
- Finding: CoreSimulatorService·simdiskimaged 가 실행 중 (`ps`). 시뮬레이터 17Gi를 미사용 캐시로 단정할 수 없음
- Finding: Claude.app PID 9047 실행 중. Application Support/Claude 12Gi는 살아있는 앱 데이터
- Decision: LLM 역할을 설명으로 한정. 정체·사용 주체 조사는 dust 상위 항목에 대해 lsof·ps·mdls가 하고, LLM은 그 증거 카드만 서술. 파일 내용과 전체 트리는 보내지 않음
- Decision: 작업 기록을 `/Users/cskim/Documents/dustsweeper/session-records/mac/261116-dust-cleanup-scan/`로 이동. `~/session-records`의 같은 경로는 위치 안내만 남김. 프로젝트 `AGENTS.md`가 이후 기록 위치를 이 폴더로 고정
