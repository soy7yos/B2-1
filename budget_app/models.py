"""데이터 모델 — Transaction(거래) · Budget(월 예산)."""
from dataclasses import dataclass, field


@dataclass
class Transaction:
    id: str
    type: str  # "income" | "expense"
    date: str  # YYYY-MM-DD
    amount: int  # 양수만 허용 (검증은 서비스 계층에서)
    category: str
    memo: str = ""
    tags: list[str] = field(default_factory=list)  # 이해_B2-1 ❓7: 내부는 list, 저장 시에만 쉼표 문자열로 직렬화


@dataclass
class Budget:
    month: str  # YYYY-MM
    amount: int
