"""Utilities to help working with JSON data."""
import json
import pathlib
from os import PathLike


def load_json(file_path: PathLike) -> dict:
    """Load JSON data from a file."""
    infile = pathlib.Path(file_path)
    with infile.open() as fp:
        return json.load(fp)


def dump_json(file_path: PathLike, force=False, **options: dict) -> PathLike:
    """Dump JSON data to a file."""
    outfile = pathlib.Path(file_path)
    if outfile.exists() and not force:
        raise FileExistsError(f"File {outfile} already exists.")

    indent = options.get("indent", 4)
    with outfile.open("w") as fp:
        json.dump(data, fp, indent=indent)

    return outfile
