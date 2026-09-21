"""서비스 계층 — 판단 로직(검증·정합성 규칙). cli.py는 입력만 해석하고 여기로 넘긴다 (§4-14 계층 분리)."""
import csv
import heapq
from datetime import datetime

CSV_FIELDS = ["date", "type", "category", "amount", "memo", "tags"]  # §4-11 고정 6열 스키마

from budget_app.decorators import AppError
from budget_app.models import Budget, Transaction
from budget_app.repository import BudgetRepository, CategoryRepository, TransactionRepository

VALID_TYPES = ("income", "expense")


class CategoryService:
    def __init__(self, category_repo: CategoryRepository, tx_repo: TransactionRepository):
        self._categories = category_repo
        self._tx = tx_repo

    def add(self, name: str) -> None:
        names = self._categories.list_categories()
        if name in names:
            # 중복 추가를 조용히 무시하면 사용자가 실수를 못 알아챈다 — 명시적으로 알림
            raise AppError(f"'{name}'은(는) 이미 있는 카테고리입니다.")
        names.append(name)
        self._categories.save_all(names)

    def list(self) -> list[str]:
        return self._categories.list_categories()

    def remove(self, name: str, replace_with: str | None) -> int:
        # 거래가 가리키는 카테고리가 사라지면 데이터 정합성이 깨진다 (§4-10: 카테고리 삭제 시 정합성 유지) — 사용 중이면 막거나 대체 카테고리로 옮긴다
        names = self._categories.list_categories()
        if name not in names:
            raise AppError(f"'{name}'은(는) 없는 카테고리입니다. 힌트: category list로 확인하세요.")

        using = [tx for tx in self._tx.stream_all() if tx.category == name]
        if using:
            if replace_with is None:
                raise AppError(
                    f"'{name}'을(를) 쓰는 거래가 {len(using)}건 있어 삭제할 수 없습니다. "
                    f"힌트: --replace-with <대체 카테고리>로 옮기고 삭제하세요."
                )
            if replace_with not in names:
                raise AppError(f"대체 카테고리 '{replace_with}'이(가) 없습니다. 힌트: category add로 먼저 만드세요.")
            if replace_with == name:
                raise AppError("대체 카테고리가 삭제할 카테고리와 같습니다.")
            all_tx = list(self._tx.stream_all())
            for tx in all_tx:
                if tx.category == name:
                    tx.category = replace_with
            self._tx.replace_all(all_tx)

        names.remove(name)
        self._categories.save_all(names)
        return len(using)


class TransactionService:
    """거래 추가 검증 + 저장. 검증 메서드는 cli의 대화형 재입력 루프에서도 직접 호출한다."""

    def __init__(self, tx_repo: TransactionRepository, category_repo: CategoryRepository):
        self._tx = tx_repo
        self._categories = category_repo

    @staticmethod
    def validate_date(text: str) -> str:
        try:
            datetime.strptime(text, "%Y-%m-%d")
        except ValueError:
            raise AppError("날짜 형식이 올바르지 않습니다 (YYYY-MM-DD). 힌트: 예: 2024-01-15")
        return text

    @staticmethod
    def validate_type(text: str) -> str:
        if text not in VALID_TYPES:
            raise AppError(f"타입은 {'/'.join(VALID_TYPES)} 중 하나여야 합니다.")
        return text

    def validate_category(self, text: str) -> str:
        # 없는 카테고리면 §4-2대로 안내만 하고 재입력을 유도 (자동 생성하지 않음)
        if text not in self._categories.list_categories():
            raise AppError(f"'{text}'은(는) 등록되지 않은 카테고리입니다. 힌트: category add로 먼저 등록하세요.")
        return text

    @staticmethod
    def validate_amount(text: str) -> int:
        try:
            amount = int(text)
        except ValueError:
            raise AppError("금액은 숫자여야 합니다.")
        if amount <= 0:
            raise AppError("금액은 0보다 큰 값이어야 합니다 (양수만 허용).")
        return amount

    def add(self, date: str, type_: str, category: str, amount: int, memo: str, tags: list[str]) -> Transaction:
        tx = Transaction(id=self._tx.next_id(date, type_), type=type_, date=date, amount=amount, category=category, memo=memo, tags=tags)
        self._tx.append(tx)
        return tx

    def update(
        self,
        tx_id: str,
        *,
        type_: str | None = None,
        date: str | None = None,
        amount: int | None = None,
        category: str | None = None,
        memo: str | None = None,
        tags: list[str] | None = None,
    ) -> Transaction:
        # 옵션 기반 update — 준 필드만 검증 후 덮어쓴다
        all_tx = list(self._tx.stream_all())
        target = next((tx for tx in all_tx if tx.id == tx_id), None)
        if target is None:
            raise AppError(f"id '{tx_id}'는 없는 데이터입니다. 힌트: list/search로 id를 확인하세요.")

        if date is not None:
            target.date = self.validate_date(date)
        if amount is not None:
            target.amount = self.validate_amount(str(amount))
        if category is not None:
            target.category = self.validate_category(category)
        if memo is not None:
            target.memo = memo
        if tags is not None:
            target.tags = tags
        if type_ is not None:
            self.validate_type(type_)
            if type_ != target.type:
                # id 앞글자만 새 type에 맞춰 교체, 뒤 8자리(날짜+순번)는 유지
                target.type = type_
                target.id = ("i" if type_ == "income" else "e") + target.id[1:]

        self._tx.replace_all(all_tx)
        return target

    def delete(self, tx_id: str) -> None:
        all_tx = list(self._tx.stream_all())
        remaining = [tx for tx in all_tx if tx.id != tx_id]
        if len(remaining) == len(all_tx):
            raise AppError(f"id '{tx_id}'는 없는 데이터입니다. 힌트: list/search로 id를 확인하세요.")
        self._tx.replace_all(remaining)

    def list_recent(self, limit: int) -> list[Transaction]:
        # sorted(list(...))는 전체를 메모리에 두 번 올린다 — heapq.nlargest는 스트림을 순회하며 상위 limit개만 유지 (§4-5 스트리밍 요건)
        return heapq.nlargest(limit, self._tx.stream_all(), key=lambda tx: (tx.date, tx.id))

    def search(
        self,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        category: str | None = None,
        type_: str | None = None,
        q: str | None = None,
        tag: str | None = None,
    ) -> list[Transaction]:
        def matches(tx: Transaction) -> bool:
            if date_from and tx.date < date_from:
                return False
            if date_to and tx.date > date_to:
                return False
            if category and tx.category != category:
                return False
            if type_ and tx.type != type_:
                return False
            if q and q not in tx.memo:
                return False
            if tag and tag not in tx.tags:
                return False
            return True

        # 제너레이터를 조건으로 필터링하며 순회 (§4-7 검색 스트리밍 요건) — 결과 집합만 리스트에 남기고 최신순 정렬
        matched = [tx for tx in self._tx.stream_all() if matches(tx)]
        matched.sort(key=lambda tx: (tx.date, tx.id), reverse=True)
        return matched

    def import_csv(self, csv_path: str) -> tuple[int, int]:
        # 한 줄씩 검증 후 통과한 줄만 저장 — 스키마 위반/없는 카테고리는 skip
        imported = 0
        skipped = 0
        with open(csv_path, encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    date = self.validate_date(row["date"])
                    type_ = self.validate_type(row["type"])
                    category = self.validate_category(row["category"])
                    amount = self.validate_amount(row["amount"])
                except (AppError, KeyError):
                    skipped += 1
                    continue
                memo = row.get("memo") or ""
                tags_raw = row.get("tags") or ""
                tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
                self.add(date, type_, category, amount, memo, tags)
                imported += 1
        return imported, skipped

    def export_csv(self, csv_path: str, *, month: str | None, date_from: str | None, date_to: str | None) -> int:
        if month:
            date_from = date_from or f"{month}-01"
            date_to = date_to or f"{month}-31"  # 문자열 비교라 31로 둬도 그 달 안이면 다 걸림 (date는 YYYY-MM-DD 포맷)
        results = self.search(date_from=date_from, date_to=date_to)
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()
            for tx in results:
                writer.writerow(
                    {
                        "date": tx.date,
                        "type": tx.type,
                        "category": tx.category,
                        "amount": tx.amount,
                        "memo": tx.memo,
                        "tags": ",".join(tx.tags),
                    }
                )
        return len(results)


class SummaryService:
    """월별 집계 + 예산 사용률. summary가 transactions·budgets 두 파일을 합쳐 읽는 지점 (§4-9: 예산 사용률 계산)."""

    def __init__(self, tx_repo: TransactionRepository, budget_repo: BudgetRepository):
        self._tx = tx_repo
        self._budget = budget_repo

    def monthly(self, month: str, top: int) -> dict:
        # 스트리밍 중 그 달 거래만 골라내고, 나머지는 즉시 버린다 (파일 전체를 들고 있지 않음)
        income = 0
        expense = 0
        by_category: dict[str, int] = {}
        count = 0
        for tx in self._tx.stream_all():
            if not tx.date.startswith(month):
                continue
            count += 1
            if tx.type == "income":
                income += tx.amount
            else:
                expense += tx.amount
                by_category[tx.category] = by_category.get(tx.category, 0) + tx.amount

        top_categories = heapq.nlargest(top, by_category.items(), key=lambda kv: kv[1])

        budget = next((b for b in self._budget.stream_all() if b.month == month), None)
        budget_info = None
        if budget is not None:
            # 사용률 = 총지출 / 예산 × 100 (§4-9: 예산 사용률 계산)
            usage_pct = round(expense / budget.amount * 100, 1) if budget.amount else 0.0
            budget_info = {"amount": budget.amount, "usage_pct": usage_pct, "over": expense > budget.amount}

        return {
            "count": count,
            "income": income,
            "expense": expense,
            "balance": income - expense,
            "top_categories": top_categories,
            "budget": budget_info,
        }
