# B2-1 — 나만의 용돈기입장 프로그램

표준 라이브러리만으로 만든 파일 입출력 기반 가계부 콘솔 프로그램. 수입·지출 CRUD에 더해 검색·월별 요약·카테고리 관리·예산 초과 경고까지 "예외 상황에서도 데이터가 안전한 작은 서비스"로 완성하는 것이 목표다. 제너레이터 스트리밍·데코레이터 분리·타입 힌트·모듈 분리로 유지보수 가능한 구조를 잡는다. (Codyssey AI 올인원 2기 · 2단계 AI 도구학습)

## 개발 환경
- Python 3.10 이상, 표준 라이브러리만 (`pip install` 없음)

## 실행 방법
```
python -m budget_app <command> [options]
python -m budget_app --help
```
(구현 완료 후 확정)

## 저장 파일 위치 / 형식
- 기본 폴더: `./data` (`--data-dir` 옵션으로 변경 가능)
- 포맷: JSONL 또는 CSV 중 택1 (구현 시 확정)
- 파일 3개 분리: `transactions.<fmt>` · `categories.<fmt>` · `budgets.<fmt>`

## 주요 명령 예시
(구현 완료 후 확정 — 요구사항 §2·§4·§8 기준)
- `add` · `list --limit N` · `search --from/--to --category --type --q --tag`
- `summary --month YYYY-MM --top N` · `budget set --month YYYY-MM --amount 금액`
- `category add/list/remove` · `update --id <id>` · `delete --id <id>`
- `import --from <csv>` · `export --out <csv> --month YYYY-MM`

## import / export CSV 스키마
| column | required | 설명 |
| --- | --- | --- |
| date | Y | YYYY-MM-DD |
| type | Y | income / expense |
| category | Y | 등록된 카테고리 |
| amount | Y | 양수 정수 |
| memo | N | 문자열 |
| tags | N | 쉼표(,) 구분 문자열 |

공통: UTF-8, 헤더 포함

## 설계 선택 (구현하며 채움)
- 저장 포맷: (JSONL / CSV 중 택1 — 왜)
- `update` 방식: (옵션 기반 / 대화형 중 택1 — 왜)
- 빈 카테고리 파일 초기 동작: (기본 카테고리 자동 생성 / `category add` 강제 중 택1 — 왜)

## 검증 방법 / logs 대응표
(각 단계 `logs/step_N_*.txt` — 구현하며 채움)
