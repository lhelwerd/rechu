"""
Script to convert a `basedpyright` output report formatted as JSON into
SonarQube server generic issuereport format.
"""

import json
import sys
from pathlib import Path
from typing import Literal, cast

from .spec.basedpyright import Diagnostic, Report
from .spec.sonar import GenericReport, Issue, Rule

SEVERITY_MAP: dict[str, Literal["CRITICAL", "MAJOR", "INFO"]] = {
    "error": "CRITICAL",
    "warning": "MAJOR",
    "information": "INFO",
}

IMPACT_MAP: dict[str, Literal["BLOCKER", "HIGH", "INFO"]] = {
    "error": "BLOCKER",
    "warning": "HIGH",
    "information": "INFO",
}


def _convert_issue(
    diagnostic: Diagnostic,
    rules: dict[str, Rule],
    issues: list[Issue],
    root: Path,
) -> None:
    if "rule" not in diagnostic:
        return

    try:
        path = Path(diagnostic["file"]).resolve().relative_to(root)
    except ValueError:
        # Ignore files outside the repository root, probably not tracked
        return

    rule = f"basedpyright_{diagnostic['rule']}"
    if rule not in rules:
        rules[rule] = {
            "id": rule,
            "name": rule,
            "description": "",
            "engineId": "basedpyright",
            "cleanCodeAttribute": "CONVENTIONAL",
            "type": "CODE_SMELL",
            "severity": SEVERITY_MAP[diagnostic["severity"]],
            "impacts": [
                {
                    "softwareQuality": "MAINTAINABILITY",
                    "severity": IMPACT_MAP[diagnostic["severity"]],
                }
            ],
        }

    issues.append(
        {
            "ruleId": rule,
            "primaryLocation": {
                "message": diagnostic["message"],
                "filePath": str(path),
                "textRange": {
                    # Diagnostic line and character numbers are zero-based
                    # However, end column is already after last character
                    "startLine": diagnostic["range"]["start"]["line"] + 1,
                    "startColumn": diagnostic["range"]["start"]["character"]
                    + 1,
                    "endLine": diagnostic["range"]["end"]["line"] + 1,
                    "endColumn": diagnostic["range"]["end"]["character"],
                },
            },
        }
    )


def main(argv: list[str]) -> int:
    """
    Main entry point.
    """

    usage = (
        "basedpyright --outputjson ... | \n"
        "  python -m scripts.format_basedpyright_report [root]"
    )
    if sys.stdin.isatty():
        print(f"Usage: {usage}", file=sys.stderr)
        return 1

    root = (
        Path(argv[1])
        if len(argv) > 1
        else Path(__file__).resolve().parent.parent
    )
    try:
        report = cast(Report, json.load(sys.stdin))
    except json.decoder.JSONDecodeError as parse_error:
        print(
            f"Could not parse report from standard input: {parse_error}",
            file=sys.stderr,
        )
        return 1

    rules: dict[str, Rule] = {}
    issues: list[Issue] = []
    for diagnostic in report["generalDiagnostics"]:
        _convert_issue(diagnostic, rules, issues, root)

    output: GenericReport = {"rules": list(rules.values()), "issues": issues}

    output_filename = "basedpyright.json"
    with Path(output_filename).open("w", encoding="utf-8") as output_path:
        json.dump(output, output_path)

    print(f"Generated SonarQube generic report in {output_filename}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
