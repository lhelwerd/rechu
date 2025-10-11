"""
Receipt cataloging module.
"""

from logging.config import dictConfig

__all__: list[str] = []
__version__ = "0.0.1"

dictConfig(
    {
        "version": 1,
        "formatters": {
            "generic_dated": {
                "format": (
                    "%(asctime)s %(levelname)-5.5s [%(name)s] %(message)s"
                ),
                "datefmt": "%Y-%m-%d %H:%M:%S",
            }
        },
        "handlers": {
            "stderr": {
                "class": "logging.StreamHandler",
                "formatter": "generic_dated",
                "stream": "ext://sys.stderr",
                "level": "NOTSET",
            }
        },
        "loggers": {__name__: {"level": "NOTSET", "handlers": ["stderr"]}},
    }
)
