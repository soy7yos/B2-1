"""공통 관심사 데코레이터 — 예외 → 원인+힌트 변환, exit code 결정 (§4-12·§4-13)."""
import functools
import sys
from collections.abc import Callable


class AppError(Exception):
    """의도적으로 발생시키는 사용자용 오류. 메시지 자체가 원인+힌트 문장이 되도록 raise 쪽에서 작성한다."""


def handle_errors(func: Callable[..., int | None]) -> Callable[..., int]:
    # 모든 명령 핸들러에 붙여 스택트레이스 대신 "원인 + 힌트"만 보여주고 exit code를 되돌린다 (§4-13).
    # 명령마다 try/except를 복붙하지 않으려고 데코레이터 하나로 모았다 (§4-12, 이해_B2-1 ❓12).
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> int:
        try:
            result = func(*args, **kwargs)
            return 0 if result is None else result
        except AppError as e:
            print(f"오류: {e}", file=sys.stderr)
            return 1
        except Exception as e:  # noqa: BLE001 - 사용자에게는 항상 힌트만 보여줘야 함
            print(f"오류: {e}", file=sys.stderr)
            print("힌트: 입력값과 --data-dir 경로를 확인하세요.", file=sys.stderr)
            return 1

    return wrapper
