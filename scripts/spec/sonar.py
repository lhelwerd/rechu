"""
Specification of Sonar generic issue format.

Types based on
https://docs.sonarsource.com/sonarqube-server/analyzing-source-code/importing-external-issues/generic-issue-import-format
"""

from typing import Literal

from typing_extensions import NotRequired, TypedDict


class Impact(TypedDict):
    """
    Sonar impact specification.
    """

    softwareQuality: Literal["SECURITY", "RELIABILITY", "MAINTAINABILITY"]
    severity: Literal["BLOCKER", "HIGH", "MEDIUM", "LOW", "INFO"]


class Rule(TypedDict):
    """
    Sonar rule specification.
    """

    id: str
    name: str
    description: str
    engineId: str
    cleanCodeAttribute: Literal[
        "FORMATTED",
        "CONVENTIONAL",
        "IDENTIFIABLE",
        "CLEAR",
        "LOGICAL",
        "COMPLETE",
        "EFFICIENT",
        "FOCUSED",
        "DISTINCT",
        "MODULAR",
        "TESTED",
        "LAWFUL",
        "TRUSTWORTHY",
        "RESPECTFUL",
    ]
    type: NotRequired[Literal["BUG", "VULNERABILITY", "CODE_SMELL"]]
    severity: NotRequired[Literal["CRITICAL", "MAJOR", "MINOR", "INFO"]]
    impacts: NotRequired[list[Impact]]


class Range(TypedDict):
    """
    Sonar text range specification.
    """

    startLine: int
    endLine: NotRequired[int]
    startColumn: NotRequired[int]
    endColumn: NotRequired[int]


class Location(TypedDict):
    """
    Sonar location specification.
    """

    message: str
    filePath: str
    textRange: Range


class Issue(TypedDict):
    """
    Sonar issue specification.
    """

    ruleId: str
    effortMinutes: NotRequired[int]
    primaryLocation: Location
    secondaryLocations: NotRequired[list[Location]]


class GenericReport(TypedDict):
    """
    Sonar generic issue import report specification.
    """

    rules: list[Rule]
    issues: list[Issue]
