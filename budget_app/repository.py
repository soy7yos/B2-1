"""저장소 계층 — JSONL 파일 읽기/쓰기. transactions·categories·budgets 3파일 분리."""
import json
import os
from collections.abc import Iterator
from dataclasses import asdict

from budget_app.models import Budget, Transaction

DEFAULT_CATEGORIES = ["식비", "교통", "주거", "통신", "급여", "기타"]  # 이해_B2-1 ❓10


def _atomic_write_lines(path: str, lines: list[str]) -> None:
    # 이해_B2-1 §4-6: 임시 파일에 다 쓴 뒤 이름만 바꿔치기 — 쓰다 중단돼도 원본 보존
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        for line in lines:
            f.write(line + "\n")
    os.replace(tmp_path, path)


class TransactionRepository:
    """거래(Transaction) 파일 I/O — 조회는 제너레이터로 스트리밍(§4-5)."""

    def __init__(self, data_dir: str):
        self._path = os.path.join(data_dir, "transactions.jsonl")
        os.makedirs(data_dir, exist_ok=True)
        if not os.path.exists(self._path):
            open(self._path, "w", encoding="utf-8").close()  # 이해_B2-1 ❓4: 없으면 자동 생성

    def stream_all(self) -> Iterator[Transaction]:
        # 파일 전체를 리스트로 올리지 않고 한 줄씩 yield (§4-5 필수 요건)
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                yield Transaction(**data)

    def append(self, tx: Transaction) -> None:
        with open(self._path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(tx), ensure_ascii=False) + "\n")

    def next_id(self, date: str, type_: str) -> str:
        # 이해_B2-1 ❓6 결정: {i|e}{YYMMDD}{그날 순번 2자리}. 순번은 수입/지출 구분 없이 그날 전체 건수를 공유해서 센다
        # (type별로 따로 세면 update로 type이 바뀔 때 다른 거래와 id가 겹칠 수 있어 이 위험을 없앰).
        prefix = "i" if type_ == "income" else "e"
        yymmdd = date[2:4] + date[5:7] + date[8:10]
        same_day = sum(1 for tx in self.stream_all() if tx.date == date)
        return f"{prefix}{yymmdd}{same_day + 1:02d}"

    def replace_all(self, transactions: list[Transaction]) -> None:
        # update/delete용 — 전체를 새로 쓰되 원자적 교체로 안전성 확보
        lines = [json.dumps(asdict(tx), ensure_ascii=False) for tx in transactions]
        _atomic_write_lines(self._path, lines)


class CategoryRepository:
    """카테고리 목록 파일 I/O."""

    def __init__(self, data_dir: str):
        self._path = os.path.join(data_dir, "categories.jsonl")
        os.makedirs(data_dir, exist_ok=True)
        if not os.path.exists(self._path):
            # 이해_B2-1 ❓3: 안 A — 빈 파일이면 기본 카테고리 자동 생성
            _atomic_write_lines(self._path, [json.dumps({"name": n}, ensure_ascii=False) for n in DEFAULT_CATEGORIES])

    def list_categories(self) -> list[str]:
        with open(self._path, encoding="utf-8") as f:
            return [json.loads(line)["name"] for line in f if line.strip()]

    def save_all(self, categories: list[str]) -> None:
        _atomic_write_lines(self._path, [json.dumps({"name": n}, ensure_ascii=False) for n in categories])


class BudgetRepository:
    """월별 예산(Budget) 파일 I/O."""

    def __init__(self, data_dir: str):
        self._path = os.path.join(data_dir, "budgets.jsonl")
        os.makedirs(data_dir, exist_ok=True)
        if not os.path.exists(self._path):
            open(self._path, "w", encoding="utf-8").close()

    def stream_all(self) -> Iterator[Budget]:
        with open(self._path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                yield Budget(**json.loads(line))

    def set_budget(self, budget: Budget) -> None:
        # 같은 month면 덮어쓰기, 아니면 추가 — 항상 전체 재작성(원자적)
        budgets = [b for b in self.stream_all() if b.month != budget.month]
        budgets.append(budget)
        lines = [json.dumps(asdict(b), ensure_ascii=False) for b in budgets]
        _atomic_write_lines(self._path, lines)
