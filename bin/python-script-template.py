#!/usr/bin/env -S uv run --script
"""A template Python script with argument parsing, logging, and error handling.

This example script is given enough functionality to make it actually do
something, but not much. Follow the patterns for the shebang, error handling
around `main`, and the signature for `main` itself. Everything else is up to
you.
"""

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic",
#     "python-dotenv",
#     "python-json-logger",
# ]
# ///

import argparse
import logging
import os
import pathlib
import sys

from functools import wraps
from enum import IntEnum
from pprint import pp
from pydantic import AnyHttpUrl
from pythonjsonlogger import jsonlogger


stderr_handler = logging.StreamHandler(stream=sys.stderr)
stderr_handler.setFormatter(
    jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
)
logging.basicConfig(level=logging.WARNING, handlers=[stderr_handler], force=True)

logger = logging.getLogger("python_script_template")


VERBOSITY_LEVELS: list[int] = [logging.WARNING, logging.INFO, logging.DEBUG]


class ExitCode(IntEnum):
    """Exit codes for the script.

    See sysexits(3) for more details.
    """

    SUCCESS = 0
    ERROR = 1
    DATAERR = 65
    NOINPUT = 66
    UNAVAILABLE = 69


class ScriptError(Exception):
    """Base exception for expected template script failures."""

    def __init__(self, message: str, exit_code: ExitCode = ExitCode.ERROR) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the script."""
    parser = argparse.ArgumentParser(
        description="Template utility script with file input and optional HTTP endpoint."
    )
    parser.add_argument(
        "-i",
        "--input-file",
        type=pathlib.Path,
        required=True,
        help="Path to the input file for this utility.",
    )
    parser.add_argument(
        "-n",
        "--target-name",
        type=str,
        required=True,
        help="Logical target name used by this utility.",
    )
    parser.add_argument(
        "--endpoint",
        type=AnyHttpUrl,
        default="http://localhost:8000",
        help="HTTP endpoint used by this utility.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase output verbosity (e.g., -v, -vv).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform a dry run without making any changes.",
    )
    parser.add_argument(
        "--debug",
        default=False,
        action="store_true",
        help="Run the script in debug mode.",
    )

    return parser


def configure_logging(verbose: int, debug: bool) -> None:
    """Set logging level from verbosity flags."""
    if debug:
        level = logging.DEBUG
    else:
        verbosity_index = min(verbose, len(VERBOSITY_LEVELS) - 1)
        level = VERBOSITY_LEVELS[verbosity_index]
    logging.getLogger().setLevel(level)
    logger.setLevel(level)


def display_env() -> None:
    print("== Utility Environment ==")
    print(f"Python version: {sys.version}")
    print(f"Python executable: {sys.executable}")
    print(f"Script path: {sys.argv[0]}")
    print(f"Module name: {__name__}")
    print("Python path")
    pp(sys.path)
    print()

    print("Environment variables:")
    pp(dict(os.environ))
    print()


def display_args(args: argparse.Namespace) -> None:
    """Display the parsed arguments for debugging purposes."""
    print("== Parsed arguments ==")
    pp(vars(args))


def error_handling(func):
    """Decorator for error handling in the main function."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ScriptError as e:
            parsed_args = args[0]
            show_stack_trace = parsed_args.debug or parsed_args.verbose > 1
            logger.error("%s", e, exc_info=show_stack_trace)
            return e.exit_code
        except Exception:
            logger.exception("An unexpected error occurred")
            return ExitCode.ERROR

    return wrapper


@error_handling
def main(args: argparse.Namespace) -> ExitCode:
    configure_logging(args.verbose, args.debug)
    logger.info("Running utility...")
    logger.debug("Input file: %s", args.input_file)
    logger.debug("Target name: %s", args.target_name)
    logger.debug("Endpoint: %s", args.endpoint)

    if not args.input_file.exists():
        raise ScriptError(f"Input file does not exist: {args.input_file}", ExitCode.NOINPUT)

    if args.debug:
        display_env()
        display_args(args)

    if args.dry_run:
        logger.info("Dry-run mode enabled; no changes will be made.")
        return ExitCode.SUCCESS

    logger.info("Template script completed successfully.")
    return ExitCode.SUCCESS


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()
    sys.exit(int(main(args)))
