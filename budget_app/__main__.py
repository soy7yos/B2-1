"""진입점. `python -m budget_app`으로 실행 — 실제 파서·핸들러는 cli.py (§4-14 계층 분리)."""
import sys

from budget_app.cli import main

if __name__ == "__main__":
    sys.exit(main())
