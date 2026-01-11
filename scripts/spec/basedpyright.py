"""
Specification of `basedpyright` output report format.

Types based on
https://github.com/DetachHead/basedpyright/blob/main/docs/configuration/command-line.md#json-output
"""

from typing import Literal

from typing_extensions import NotRequired, TypedDict


class Position(TypedDict):
    """
    Location of diagnostic of basedpyright.
    """

    line: int
    character: int


class Range(TypedDict):
    """
    Locations of diagnostic of basedpyright.
    """

    start: Position
    end: Position


class Diagnostic(TypedDict):
    """
    Diagnostic error report of basedpyright.
    """

    file: str
    cell: NotRequired[str]
    severity: Literal["error", "warning", "information"]
    message: str
    rule: NotRequired[str]
    range: Range


class Summary(TypedDict):
    """
    Summary report of basedpyright.
    """

    filesAnalyzed: int
    errorCount: int
    warningCount: int
    informationCount: int
    timeInSec: int


class Report(TypedDict):
    """
    Output report of basedpyright.
    """

    version: str
    time: str
    generalDiagnostics: list[Diagnostic]
    summary: Summary
