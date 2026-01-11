"""
Script to convert a `check-jsonschema` output report formatted as JSON into
SonarQube server generic issue report format.
"""

import json
import re
import sys
from pathlib import Path
from typing import cast

from .spec.jsonschema import Error, ParseError, Report as SchemaReport
from .spec.sonar import GenericReport, Issue, Location, Rule

ERROR_FILTER = re.compile(r"\d\.\d\d? is not a multiple of 0\.01")


def _parse_error(
    schema: str,
    rules: dict[str, Rule],
    issues: list[Issue],
    error: Error | ParseError,
    root: Path,
) -> None:
    if schema == "schema/receipt.json" and ERROR_FILTER.match(error["message"]):
        return

    try:
        path = Path(error["filename"]).resolve().relative_to(root)
    except ValueError:
        # Ignore files outside the repository root, probably not tracked
        return

    location: Location = {
        "message": error["message"],
        "filePath": str(path),
        "textRange": {"startLine": 1},
    }
    json_path = error.get("path")
    if json_path is not None:
        rules["json_validate_error"] = {
            "id": "json_validate_error",
            "name": "JSON schema validation error",
            "description": "JSON schema detected a nonconforming element.",
            "engineId": "check-jsonschema",
            "cleanCodeAttribute": "CONVENTIONAL",
            "impacts": [{"softwareQuality": "RELIABILITY", "severity": "LOW"}],
            "type": "BUG",
            "severity": "MINOR",
        }
        location["message"] = f"{error['message']}. JSON path: {json_path}"
        issues.append(
            {"ruleId": "json_validate_error", "primaryLocation": location}
        )
    else:
        rules["json_parse_error"] = {
            "id": "json_parse_error",
            "name": "JSON schema parsing error",
            "description": "A JSON, TOML or YAML file could not be parsed.",
            "engineId": "check-jsonschema",
            "cleanCodeAttribute": "LOGICAL",
            "impacts": [{"softwareQuality": "RELIABILITY", "severity": "HIGH"}],
            "type": "BUG",
            "severity": "MAJOR",
        }

        # Locate the parse error by parsing the affected file ourselves
        try:
            with Path(error["filename"]).open(
                "r", encoding="utf-8"
            ) as parse_file:
                json.load(parse_file)
        except json.decoder.JSONDecodeError as parse_error:
            location["message"] = f"Failed to parse file: {parse_error.msg}"
            location["textRange"] = {
                "startLine": parse_error.lineno,
                "startColumn": parse_error.colno,
            }

        issues.append(
            {"ruleId": "json_parse_error", "primaryLocation": location}
        )


def main(argv: list[str]) -> int:
    """
    Main entry point.
    """

    usage = (
        "check-jsonschema --output-format json ... | \n"
        "  python -m scripts.format_json_schema_report <schema> [root]"
    )
    if not argv or sys.stdin.isatty():
        print(f"Usage: {usage}", file=sys.stderr)
        return 1

    schema = argv[0]
    root = (
        Path(argv[1])
        if len(argv) > 1
        else Path(__file__).resolve().parent.parent
    )
    report: SchemaReport
    try:
        report = cast(SchemaReport, json.load(sys.stdin))
    except json.decoder.JSONDecodeError as report_error:
        print(
            f"Could not parse report from standard input: {report_error}",
            file=sys.stderr,
        )
        report = {
            "status": "fail",
            "parse_errors": [{"filename": schema, "message": ""}],
        }

    rules: dict[str, Rule] = {}
    issues: list[Issue] = []
    for error in report.get("errors", []):
        _parse_error(schema, rules, issues, error, root)
    for parse_error in report.get("parse_errors", []):
        _parse_error(schema, rules, issues, parse_error, root)

    output: GenericReport = {"rules": list(rules.values()), "issues": issues}

    output_filename = f"jsonschema_report_{Path(schema).stem}.json"
    with Path(output_filename).open("w", encoding="utf-8") as output_path:
        json.dump(output, output_path)

    print(f"Generated SonarQube generic report in {output_filename}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
