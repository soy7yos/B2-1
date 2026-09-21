# B2-1 — 나만의 용돈기입장 프로그램

표준 라이브러리만으로 만든 파일 입출력 기반 가계부 콘솔 프로그램. 수입·지출 CRUD에 더해 검색·월별 요약·카테고리 관리·예산 초과 경고까지 "예외 상황에서도 데이터가 안전한 작은 서비스"로 완성하는 것이 목표다. 제너레이터 스트리밍·데코레이터 분리·타입 힌트·모듈 분리로 유지보수 가능한 구조를 잡는다. (Codyssey AI 올인원 2기 · 2단계 AI 도구학습)

## 개발 환경
- Python 3.10 이상, 표준 라이브러리만 (`pip install` 없음)

## 실행 방법
```
python -m budget_app <command> [options]
python -m budget_app <command> --help
```
전역 옵션 `--data-dir`(기본값 `./data`)는 서브커맨드 앞에 붙인다: `python -m budget_app --data-dir ./mydata add`

## 저장 파일 위치 / 형식
- 기본 폴더: `./data` (`--data-dir` 옵션으로 변경 가능)
- 포맷: **JSONL** (한 줄에 레코드 하나 — 제너레이터로 한 줄씩 읽는 스트리밍 요건과 맞아떨어져 선택)
- 파일 3개 분리:
  - `transactions.jsonl` — 거래 내역
  - `categories.jsonl` — 카테고리 목록
  - `budgets.jsonl` — 월별 예산
- 저장 파일이 없을 때: 별도 안내 없이 **자동 생성**. `categories.jsonl`은 기본 카테고리 6개로 채워서 생성, `transactions.jsonl`/`budgets.jsonl`은 빈 파일로 생성

## 구현 기능 목록
- `add` — 거래 추가 (대화형 입력, 검증 실패 시 같은 항목 재입력)
- `list --limit N` — 최신순 목록 (기본 5건)
- `search --from/--to --category --type --q --tag` — 조건 검색
- `update --id <id> [--type --date --amount --category --memo --tags]` — 옵션 기반 수정
- `delete --id <id>` — 삭제
- `summary --month YYYY-MM [--top N]` — 월별 총수입/총지출/잔액 + 지출 상위 카테고리(기본 top 3) + 예산 사용률
- `budget set --month YYYY-MM --amount <금액>` — 월 예산 설정
- `category add/list/remove [--replace-with]` — 카테고리 관리 (사용 중인 카테고리는 기본 삭제 차단, `--replace-with`로 대체 카테고리 지정 시 거래를 옮긴 뒤 삭제)
- `import --from <csv>` — CSV 일괄 등록 (검증 실패 줄은 skip, 건수 집계)
- `export --out <csv> (--month | --from/--to)` — 조건에 맞는 거래를 CSV로 저장

## 주요 명령 예시
```
python -m budget_app add
python -m budget_app list --limit 10
python -m budget_app search --from 2026-01-01 --to 2026-01-31 --type expense
python -m budget_app update --id e26011501 --amount 15000
python -m budget_app delete --id e26011501
python -m budget_app summary --month 2026-01 --top 3
python -m budget_app budget set --month 2026-01 --amount 500000
python -m budget_app category add 문화생활
python -m budget_app category remove 문화생활 --replace-with 기타
python -m budget_app import --from backup.csv
python -m budget_app export --out backup.csv --month 2026-01
```

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

## 설계 선택
- **저장 포맷: JSONL.** CSV는 표 구조라 태그 같은 가변 길이 필드를 다루기 번거롭고, JSONL은 한 줄 = 레코드 하나라 `stream_all()` 제너레이터로 한 줄씩 읽는 스트리밍 요건(§4-5)과 자연스럽게 맞는다.
- **`update` 방식: 옵션 기반.** `delete --id`와 방식을 통일해 스크립트로도 호출 가능하게 하고, 대화형 재입력 로직(add에서 씀)을 update까지 넓히면 "일부 필드만 바꾸고 싶다"는 흔한 경우에 오히려 불편해서 배제.
- **빈 카테고리 파일 초기 동작: 안 A(기본 카테고리 자동 생성).** `category add`를 강제하면 `add` 첫 실행부터 막혀 진입장벽이 생기므로, 식비/교통/주거/통신/급여/기타 6개를 자동 생성해 바로 쓸 수 있게 함.

## 자유 선택 기준값
- `list --limit` 기본값: 5
- `summary --top` 기본값: 3
- 기본 카테고리: 식비, 교통, 주거, 통신, 급여, 기타
- `id` 형식: `{i|e}{YYMMDD}{그날 순번 2자리}` (예: 수입/지출 구분 없이 그날 전체 건수로 순번을 매겨 type 변경 시에도 겹치지 않게 함)
- `--data-dir` 기본값: `./data`

## 검증 방법 / logs 대응표
| 단계 | 내용 | 로그 |
| --- | --- | --- |
| 1 | 패키지 뼈대 + 모델 | `logs/step_1_skeleton.txt` |
| 2 | 저장소 계층 | `logs/step_2_repo.txt` |
| 3 | CLI 파서 + 데코레이터 + 예외/exit code | `logs/step_3_cli.txt` |
| 4 | category 관리 | `logs/step_4_category.txt` |
| 5 | add + 입력 검증 | `logs/step_5_add.txt` |
| 6 | list + search | `logs/step_6_list_search.txt` |
| 7 | update + delete | `logs/step_7_update_delete.txt` |
| 8 | summary + budget | `logs/step_8_summary_budget.txt` |
| 9 | import + export | `logs/step_9_import_export.txt` |
