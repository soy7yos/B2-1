"""CLI 파서 — 서브커맨드 정의만 담당, 판단 로직은 4~9단계에서 서비스 계층으로 뺀다 (§4-14 계층 분리)."""
import argparse
import sys
from collections.abc import Callable

from budget_app.decorators import AppError, handle_errors
from budget_app.repository import CategoryRepository, TransactionRepository
from budget_app.service import CategoryService, TransactionService

_NOT_IMPLEMENTED = "이 기능은 아직 구현되지 않았습니다 (다음 단계에서 추가 예정)"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="budget_app",
        description="터미널 용돈기입장 프로그램 - 수입/지출을 기록하고 요약한다.",
    )
    # 옵션 대시는 --로 통일 (이해_B2-1 ❓1). --data-dir 기본값은 ./data (❓11).
    parser.add_argument("--data-dir", default="./data", help="데이터 파일 폴더 (기본값: ./data)")
    sub = parser.add_subparsers(dest="command", required=True)

    p_add = sub.add_parser("add", help="거래 추가 (대화형)")
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list", help="거래 목록 (최신순)")
    p_list.add_argument("--limit", type=int, default=5, help="보여줄 최대 개수 (기본값: 5)")
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser("search", help="조건으로 거래 검색")
    p_search.add_argument("--from", dest="date_from", help="검색 시작일 YYYY-MM-DD")
    p_search.add_argument("--to", dest="date_to", help="검색 종료일 YYYY-MM-DD")
    p_search.add_argument("--category", help="카테고리")
    p_search.add_argument("--type", choices=["income", "expense"], help="income 또는 expense")
    p_search.add_argument("--q", help="메모 키워드")
    p_search.add_argument("--tag", help="태그")
    p_search.set_defaults(func=cmd_search)

    p_summary = sub.add_parser("summary", help="월별 총수입/총지출/잔액 + 카테고리 TOP N")
    p_summary.add_argument("--month", required=True, help="YYYY-MM")
    p_summary.add_argument("--top", type=int, default=3, help="지출 상위 카테고리 개수 (기본값: 3)")
    p_summary.set_defaults(func=cmd_summary)

    p_budget = sub.add_parser("budget", help="월 예산 설정")
    budget_sub = p_budget.add_subparsers(dest="budget_command", required=True)
    p_budget_set = budget_sub.add_parser("set", help="월 예산 저장")
    p_budget_set.add_argument("--month", required=True, help="YYYY-MM")
    p_budget_set.add_argument("--amount", type=int, required=True, help="예산 금액")
    p_budget_set.set_defaults(func=cmd_budget_set)

    p_category = sub.add_parser("category", help="카테고리 관리")
    category_sub = p_category.add_subparsers(dest="category_command", required=True)
    p_cat_add = category_sub.add_parser("add", help="카테고리 추가")
    p_cat_add.add_argument("name")
    p_cat_add.set_defaults(func=cmd_category_add)
    p_cat_list = category_sub.add_parser("list", help="카테고리 목록")
    p_cat_list.set_defaults(func=cmd_category_list)
    p_cat_remove = category_sub.add_parser("remove", help="카테고리 삭제")
    p_cat_remove.add_argument("name")
    # 사용 중인 카테고리는 기본적으로 삭제 차단 — 옮길 곳을 명시해야 삭제 허용 (이해_B2-1 §4-10)
    p_cat_remove.add_argument("--replace-with", help="사용 중인 거래를 옮길 대체 카테고리")
    p_cat_remove.set_defaults(func=cmd_category_remove)

    # update는 옵션 기반으로 고정 (이해_B2-1 ❓5) — delete와 방식 통일
    p_update = sub.add_parser("update", help="거래 수정 (옵션 기반)")
    p_update.add_argument("--id", required=True)
    p_update.add_argument("--type", choices=["income", "expense"])
    p_update.add_argument("--date")
    p_update.add_argument("--amount", type=int)
    p_update.add_argument("--category")
    p_update.add_argument("--memo")
    p_update.add_argument("--tags", help="쉼표(,) 구분")
    p_update.set_defaults(func=cmd_update)

    p_delete = sub.add_parser("delete", help="거래 삭제")
    p_delete.add_argument("--id", required=True)
    p_delete.set_defaults(func=cmd_delete)

    p_import = sub.add_parser("import", help="CSV에서 거래 일괄 등록")
    p_import.add_argument("--from", dest="csv_path", required=True, help="가져올 CSV 파일 경로")
    p_import.set_defaults(func=cmd_import)

    p_export = sub.add_parser("export", help="조건에 맞는 거래를 CSV로 저장")
    p_export.add_argument("--out", required=True, help="내보낼 CSV 파일 경로")
    p_export.add_argument("--month", help="YYYY-MM (또는 --from/--to 사용)")
    p_export.add_argument("--from", dest="date_from", help="YYYY-MM-DD")
    p_export.add_argument("--to", dest="date_to", help="YYYY-MM-DD")
    p_export.set_defaults(func=cmd_export)

    return parser


# 아래 핸들러는 3단계 범위(파서+데코레이터+예외처리) 확인용 스텁이다. 4~9단계에서 서비스 계층 호출로 교체한다.


def _prompt_retry(prompt_text: str, validator: Callable[[str], object]) -> object:
    # §4-2 "재입력 요구"를 대화형으로 구현 — 검증 실패해도 프로그램을 끝내지 않고 같은 질문을 다시 던진다
    while True:
        raw = input(prompt_text)
        try:
            return validator(raw)
        except AppError as e:
            print(f"[오류] {e}", file=sys.stderr)


@handle_errors
def cmd_add(args: argparse.Namespace) -> int:
    service = _tx_service(args)

    date = _prompt_retry("날짜(YYYY-MM-DD): ", TransactionService.validate_date)
    type_ = _prompt_retry("타입(income/expense): ", TransactionService.validate_type)
    category = _prompt_retry("카테고리: ", service.validate_category)
    amount = _prompt_retry("금액(양수): ", TransactionService.validate_amount)
    memo = input("메모(선택): ").strip()
    tags_raw = input("태그(쉼표로 구분, 없으면 엔터): ").strip()
    # 내부 표현은 list[str] (이해_B2-1 ❓7) — CSV 직렬화는 9단계 import/export에서 처리
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

    tx = service.add(date, type_, category, amount, memo, tags)
    print(f"[저장 완료] id={tx.id}")


def _print_tx(tx) -> None:
    # §8 예시 형식(id | date | type | category | amount | memo) 그대로 — tags는 search --tag로만 걸러보고 목록엔 안 찍음
    print(f"{tx.id} | {tx.date} | {tx.type} | {tx.category} | {tx.amount} | {tx.memo}")


def _tx_service(args: argparse.Namespace) -> TransactionService:
    return TransactionService(TransactionRepository(args.data_dir), CategoryRepository(args.data_dir))


@handle_errors
def cmd_list(args: argparse.Namespace) -> int:
    results = _tx_service(args).list_recent(args.limit)
    if not results:
        print("거래 내역이 없습니다.")
        return
    for tx in results:
        _print_tx(tx)


@handle_errors
def cmd_search(args: argparse.Namespace) -> int:
    results = _tx_service(args).search(
        date_from=args.date_from,
        date_to=args.date_to,
        category=args.category,
        type_=args.type,
        q=args.q,
        tag=args.tag,
    )
    if not results:
        print("검색 결과가 없습니다.")
        return
    for tx in results:
        _print_tx(tx)


@handle_errors
def cmd_summary(args: argparse.Namespace) -> int:
    raise AppError(_NOT_IMPLEMENTED)


@handle_errors
def cmd_budget_set(args: argparse.Namespace) -> int:
    raise AppError(_NOT_IMPLEMENTED)


def _category_service(args: argparse.Namespace) -> CategoryService:
    return CategoryService(CategoryRepository(args.data_dir), TransactionRepository(args.data_dir))


@handle_errors
def cmd_category_add(args: argparse.Namespace) -> int:
    _category_service(args).add(args.name)
    print(f"카테고리 '{args.name}' 추가 완료")


@handle_errors
def cmd_category_list(args: argparse.Namespace) -> int:
    for name in _category_service(args).list():
        print(name)


@handle_errors
def cmd_category_remove(args: argparse.Namespace) -> int:
    moved = _category_service(args).remove(args.name, args.replace_with)
    if moved:
        print(f"카테고리 '{args.name}' 삭제 완료 (거래 {moved}건을 '{args.replace_with}'로 이동)")
    else:
        print(f"카테고리 '{args.name}' 삭제 완료")


@handle_errors
def cmd_update(args: argparse.Namespace) -> int:
    raise AppError(_NOT_IMPLEMENTED)


@handle_errors
def cmd_delete(args: argparse.Namespace) -> int:
    raise AppError(_NOT_IMPLEMENTED)


@handle_errors
def cmd_import(args: argparse.Namespace) -> int:
    raise AppError(_NOT_IMPLEMENTED)


@handle_errors
def cmd_export(args: argparse.Namespace) -> int:
    raise AppError(_NOT_IMPLEMENTED)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
