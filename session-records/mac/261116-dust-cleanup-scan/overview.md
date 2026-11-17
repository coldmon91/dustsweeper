---
created: 2026-11-16
updated: 2026-11-16
project: none
keys: [dust, Ollama.app, Rancher Desktop.app, Xcode.app, CoreSimulator]
---
# dust-cleanup-scan — 로컬 디스크 대용량 후보

- Request: dust로 용량이 큰 불필요 프로그램 삭제 후보를 추리고, dust+LLM 정리 스크립트 아이디어를 평가
- Result: Data 볼륨 319Gi 사용·116Gi 여유. 홈 262Gi 중 큰 몫은 앱 번들이 아니라 Library·캐시·모델·업무 트리. 삭제 판단은 LLM이 아니라 규칙+근거가 맡아야 함
- Follow-up: dust 상위 항목에 lsof·ps·mdls 증거 카드를 붙이는 리포트 스크립트를 만들지 확인
