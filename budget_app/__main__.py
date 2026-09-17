"""진입점. `python -m budget_app`으로 실행 — cli.py는 3단계에서 추가."""
import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="budget_app",
        description="터미널 용돈기입장 - 수입/지출을 기록하고 요약한다.",
    )
    parser.parse_args()
    return 0


if __name__ == "__main__":
    sys.exit(main())
