"""Small command line helper.

    python -m app.cli check ../samples/concave_broken_questionnaire.txt

Prints every problem with its line number. Exit code: 0 = no errors, 1 = errors, 2 = file not readable.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.questionnaire import check_questionnaire


def check(path: Path) -> int:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        print(f"Cannot read {path}: {exc.strerror or exc}")
        return 2
    except UnicodeDecodeError:
        print(f"Cannot read {path}: it is not a UTF-8 text file.")
        return 2

    result = check_questionnaire(text)
    print(f"Checking {path.name}")
    if result.survey is not None:
        s = result.survey
        print(f"Survey '{s.sid}' ({s.title}): {len(s.questions)} questions, {len(s.quotas)} quotas")
    print()
    for issue in result.issues:
        print(f"  Line {issue.line:<4} {issue.severity.upper():<8} {issue.message}")

    errors, warnings = len(result.errors), len(result.warnings)
    if result.issues:
        print()
    if errors:
        print(f"Result: {errors} error(s), {warnings} warning(s). Fix the errors before this survey can be approved.")
        return 1
    print(f"Result: no errors, {warnings} warning(s). Ready for preview and approval.")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Survey text can contain any language; never crash the console on printing it.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Questionnaire tools.")
    commands = parser.add_subparsers(dest="command", required=True)
    check_cmd = commands.add_parser("check", help="read and check a questionnaire .txt file")
    check_cmd.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    return check(args.file)


if __name__ == "__main__":
    sys.exit(main())
