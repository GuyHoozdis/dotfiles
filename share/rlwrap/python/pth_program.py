#!/usr/bin/env python3
"""Compile / decompile the one-line pth progam pattern.
"""
import argparse
import io
import json
import os
import re
import sys

from collections import namedtuple


__version__ = '0.1.0'


def read_pth_file(filepath):
    #if isinstance(filepath, io.TextIOWrapper):
    if isinstance(filepath, io.IOBase):
        contents = filepath.readlines()
    else:
        with open(filepath, 'r') as istream:
            contents = istream.readlines()
    return contents[0] if len(contents) == 1 else contents


def decompile_one_line_pth_program(contents, ostream):
    """Parse the one-line program as a string pattern used by *.pth files

    There is a line in the documentation for the `site` module; "Lines
    starting with import (followed by space or tab) are executed."

    A more generic and robust way to dump these programs would be to use
    the `compile` builtin and `ast` module.  There are third-party tools
    to turn go the other way.

        https://greentreesnakes.readthedocs.io/en/latest/tofrom.html
    """
    if 1 ==  contents.count(';'):
        # This is the most common approach.  A few standard imports, a semi-
        # colon, and then an exec command that wraps a long string.  All of
        # this exists on a single line in a *.pth file.

        # "import os, sys;exec(..."
        imports, execstring = contents.split(';')
        # strip "exec(" off the front and ")" off the back of the string,
        # evaluate the resulting string to remove one level of escapes
        program = eval(execstring[5:-1])
        program = [imports + os.linesep, eval(execstring[5:-1])]

    elif 0 != contents.count(';'):
        # Less common.  This form is a series of statements delimited by a
        # semi-colon.  There probably still could be logic/control flow
        # statements too, but
        program = [line + os.linesep for line in  contents.split(';')]

    else:
        # I haven't seen anything other than the two forms handled above. If it
        # is not one of those, let's be noisey so that I can look into it.
        raise ValueError("Unknown program representation")

    return ostream.writelines(program)


def compile_into_one_line_pth_program(contents, ostream):
    # Take the first line, imports, rstrip() any newline (it will never use
    # one), and complete the import statement with a semi-colon.  This pattern
    # will be the same for every technique seen thus far.
    SourceCode = namedtuple('SourceCode', ['lineno', 'indention', 'code'])
    program = [SourceCode(0, 0, contents[0].rstrip() + ';')]

    # Determine which format needs to be generated: a series of semi-colon
    # delimited statements or small bit of logic with control flow statements
    starts_with_whitespace = re.compile(r'^[\s]+')
    program += [
        SourceCode(lineno, len(match.group() if match else []), line)
        for lineno, match, line in [
            (idx+1, starts_with_whitespace.match(line.rstrip()), line)
            for idx, line in enumerate(contents[1:])
        ]
    ]
    has_indention = any([source_code.indention for source_code in program])

    # If there is no indention, then we will write the reset of the lines
    if not has_indention:
        def append_semicolon_if_line_not_empty(source):
            return source.code.rstrip() + ';' if source.code.rstrip() else ''

        import_statement = program[0].code
        one_line_program = ''.join([
            append_semicolon_if_line_not_empty(source)
            for source in program[1:]
        ]) + os.linesep
        written = ostream.write(import_statement + one_line_program)
        # XXX: The original doesn't have a ';' after the last statement.  That
        # means that they probably ';'.join(statements) to build the parts
        # after the imports.  I'l come back and examine that.
    else:
        import ipdb; ipdb.sset_trace();  # Breakpoint
        execstr = ''.join([source.code for source in program[1:]])
        execstr = 'exec(\'' + execstr + '\')'
        # Leverage the json library to escape the string
        source = program[0].code + execstr
        source = json.dumps(source)
        # XXX: Left off here

    return written


def create_parser():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        '--version', action='version', version='v' + __version__,
        help="Display the version number",
    )
    parser.add_argument(
        'istream', metavar='FILENAME', default='-',
        type=argparse.FileType('r'), nargs=argparse.OPTIONAL,
        help="Read Content to be compiled or decompiled",
    )
    parser.add_argument(
        '-o', '--ostream', metavar='FILENAME', default=sys.stdout,
        type=argparse.FileType('x'), nargs=argparse.OPTIONAL,
        help="Write the compiled or decompiled program",
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '-d', '--decompile', action='store_true', dest='decompile',
        help="Turn a one-line pth pattern into a python program",
    )
    group.add_argument(
        '-c', '--compile', action='store_false', dest='decompile',
        help="Turn a standard program into the one-line pth pattern",
    )

    return parser


DISPATCH = {
    'decompile': decompile_one_line_pth_program,
    'compile': compile_into_one_line_pth_program,
}


def main(args):
    """Apply the selected transform to the input file contents"""
    contents = read_pth_file(args.istream)
    transform = DISPATCH['decompile' if args.decompile else 'compile']
    written = transform(contents, args.ostream)
    return not written


#
#
#


from os import path
from collections import OrderedDict, Mapping
def debug_scenario_generator():
    class Solution(object):
        format_read_error = "Failed to read contents: {}".format

        def __init__(self, filename):
            self._filename = filename
            self._contents = None

        @classmethod
        def load_solution_from_file(cls, filename):
            assert path.isfile(filename)
            sln = cls(filename)
            if not sln.read_file_contents():
                error_message = cls.format_read_error(filename)
                raise ValueError(error_message, filename)
            return sln

        def read_file_contents(self, reload=False):
            if not self._contents or reload:
                with open(self._filename) as istream:
                    self._contents = istream.readlines()
            return bool(self._contents)

        @property
        def filename(self):
            return self._filename

        @property
        def contents(self):
            return self._contents[:]

    # Scenario
    # | - args                  : The commandline args
    # | - application
    # |   | - transform         : The transform method
    # |   | - written           : The bytes written
    # |   | - program
    # |   |   | - original      : Source as read in by the application
    # |   |   | - transformed   : The transformed source code
    # | - solution              : The expected transform output
    Scenario = namedtuple('Scenario', ['args', 'application', 'solution'])
    ApplicationState = namedtuple(
        'ApplicationState', ['program', 'transform', 'written']
    )
    SourceCode = namedtuple('SourceCode', ['original', 'transformed'])

    scenario_inputs = [
        (create_parser().parse_args([switch, infile]), solutionfile)
        for switch, infile, solutionfile in [
            ('--decompile',
             'examples/configparser-3.5.0-py2.7-nspkg.pth',
             'examples/configparser-3.5.0-py2.7-nspkg-pth.py'),
            ('--compile',
             'examples/pytest-cov-pth.py',
             'examples/pytest-cov.pth'),
            ('--decompile',
             'examples/configparser-3.5.0-py2.7-nspkg.pth',
             'examples/configparser-3.5.0-py2.7-nspkg-pth.py'),
            ('--compile',
             'examples/pytest-cov.pth',
             'examples/pytest-cov-pth.py'),
        ]
    ]

    for args, solutionfile in scenario_inputs:
        transform = DISPATCH['decompile' if args.decompile else 'compile']
        original_contents = read_pth_file(args.istream)
        ostream= io.StringIO()
        written = transform(original_contents, ostream)
        source_code = SourceCode(original_contents, ostream.getvalue())
        application = ApplicationState(source_code, transform, written)
        solution = Solution.load_solution_from_file(solutionfile)
        yield Scenario(args, application, solution)


if __name__ == '__main__':
    parser = create_parser()
    args = parser.parse_args()
    sys.exit(main(args))
