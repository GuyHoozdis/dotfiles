"""Utilities to help with CSV files."""
import csv
import pathlib

from os import PathLike
from typing import Iterable


DictRow = dict[str, str]


def load_csv(file_path: PathLike, encoding="UTF-8") -> Iterable[DictRow]:
    """Load a CSV file and return a list of dictionaries.

    Args:
        file_path (PathLike): The path to the CSV file.

    Returns:
        Iterable[DictRow]: A list of dictionaries representing the rows in the CSV file.
    """
    infiles = pathlib.Path().glob(str(file_path))
    for infile in infiles:
        with infile.open(encoding=encoding) as fp:
            reader = csv.DictReader(fp)
            yield from reader

