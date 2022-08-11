import pytest

from os import path

from pth_program import


def verify_external_fixtures_exist(filepath):
    if path.isfile(filepath):
        return
    format_message = "Failed to locate: {}".format
    pytest.xfail(format_message(filepath))


def test_decompile_exec_string_style():
    infile = 'examples/pytest-cov.pth'
    verify_external_fixtures_exist(infile)

    assert True
