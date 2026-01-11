"""
Specifications of `check-jsonschema` JSON reporter output format.
"""

from typing import Literal

from typing_extensions import NotRequired, TypedDict


class ErrorMatch(TypedDict):
    """
    JSON schema error match specification.
    """

    path: str
    message: str


class Error(ErrorMatch):
    """
    JSON schema error specification.
    """

    filename: str
    has_sub_errors: bool
    best_match: NotRequired[ErrorMatch]
    best_deep_match: NotRequired[ErrorMatch]
    num_sub_errors: NotRequired[int]
    sub_errors: NotRequired[list[ErrorMatch]]


class ParseError(TypedDict):
    """
    Parse error specification.
    """

    filename: str
    message: str


class Report(TypedDict):
    """
    JSON schema report specification.
    """

    status: Literal["fail", "ok"]
    successes: NotRequired[list[str]]
    checked_paths: NotRequired[list[str]]
    errors: NotRequired[list[Error]]
    parse_errors: NotRequired[list[ParseError]]
