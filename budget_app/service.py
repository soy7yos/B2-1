"""서비스 계층 — 판단 로직(검증·정합성 규칙). cli.py는 입력만 해석하고 여기로 넘긴다 (§4-14 계층 분리)."""
from budget_app.decorators import AppError
from budget_app.repository import CategoryRepository, TransactionRepository


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
        # 거래가 가리키는 카테고리가 사라지면 데이터 정합성이 깨진다 (이해_B2-1 §4-10) — 사용 중이면 막거나 대체 카테고리로 옮긴다
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
