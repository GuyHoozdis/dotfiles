#!/usr/bin/env -S uv run --script
"""A template Python script with argument parsing, logging, and error handling.

This example script is given enough functionality to make it acutally do
something, but not much.  Follow the patterns for the shabang, error handling
around `main`, and the signature for `main` itself.  Everything else is up to
you.
"""

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pydantic",
#     "python-dotenv",
# ]
# ///

import argparse
import logging
import os
import pathlib
import sys

from enum import IntEnum
from pprint import pp
from pydantic import AnyHttpUrl


logging.basicConfig(
    format="[%(levelname)-8s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
)

logger = logging.getLogger("vdb_utils")


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


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the script."""
    parser = argparse.ArgumentParser(description="Load data into ChromaDB from a JSON file.")
    parser.add_argument(
        "-d",
        "--data-file",
        type=pathlib.Path,
        required=True,
        help="Path to the input JSON file containing documents.",
    )
    parser.add_argument(
        "-c",
        "--collection-name",
        type=str,
        required=True,
        help="Name of the ChromaDB collection to load data into.",
    )
    parser.add_argument(
        "--chroma",
        type=AnyHttpUrl,
        default="http://localhost:8002",
        help="URL of the ChromaDB server.",
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



def display_env(args: argparse.Namespace) -> None:
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

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except DataLoadError as e:
            show_stack_trace = True if args[0].verbose > 1 else False
            logger.error("Failed to load data", exc_info=show_stack_trace)
            return e.exit_code
        except Exception as e:
            logger.exception("An unexpected error occurred: %s", e)
            return ExitCode.ERROR

    return wrapper


def main(args: argparse.Namespace) -> int:
    print("Running utility...")
    display_env(args)
    display_args(args)


if __name__ == "__main__":
    parser = create_parser()
    args = parser.parse_args()
    try:
        rc = main(args)
    except DataLoadError as e:
        show_stack_trace = True if args.verbose > 1 else False
        logger.error("Failed to load data", exc_info=show_stack_trace)
        rc = e.exit_code
    except Exception as e:
        logger.exception("An unexpected error occurred: %s", e)
        rc = ExitCode.ERROR
    sys.exit(rc)

