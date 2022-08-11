#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Pretty Print Chrome Dev Tools Curl Commands

Capture a network trace using Chrome Dev Tools and then dump preserve the data
by saving as a series of curl commands.

    https://developers.google.com/web/tools/chrome-devtools/network-performance/reference#copy

That content can be written to file or piped into this utility directly.
Assuming you have the curl commands on your clipboard (see the link above) or
have pasted that content, the un-formatted curl queries, into a file; the
following examples will format those curl commands into a more human-friendly
format.  In

    (1) $ pbpaste | format_curl.py network_trace.curl
    (2) $ format_curl.py path/to/raw_trace.curl network_trace.curl
    (3) $ cat path/to/*.curl | format_curl.py | lnav
    (4) $ pbpaste | tail -1 | format_curl.py redo.curl && bash redo.curl
    (5) $ bash -c "$(pbpaste | tail -1 | format_curl.py)"

(1) From clipboard into the utility and written to file "network_trace.curl".
(2) From file "raw_trace.curl" formatted and written to "network_trace.curl".
(3) Pipe formatted output into a pager for even more beautification!
(4) Take the last curl command, format it, write it to "redo.curl", and then
    execute it.  The saved file can be executed over and over.
(5) Similar to (4); except no local file is written.  Running this again
    requires the entire command to be evaluated again.
"""
import argparse
import glob
import os
import re
import sys


def pretty_print_curl_command(line):
    replacement = r' \\\n\t\g<opt>'
    pattern = re.compile(r'(?P<space>[ ])(?P<opt>\-{1,2}[\w\-]+)')
    return pattern.sub(replacement, line)


def main(args):
    for line in args.infile.readlines():
        formatted_line = pretty_print_curl_command(line)
        args.outfile.write(formatted_line)
        args.outfile.write(os.linesep)


def create_parser():
    lines = __doc__.split(os.linesep)
    description, epilog = lines[0], os.linesep.join(lines[1:])
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=os.linesep.join([description, '-'*len(description)]),
        epilog=epilog,
    )
    parser.add_argument(
        "infile", type=argparse.FileType('r'), nargs=argparse.OPTIONAL,
        help="A file containing the curl commands copiedfrom Chrome Dev Tools",
        default=sys.stdin,
    )
    parser.add_argument(
        'outfile', type=argparse.FileType('w'), nargs=argparse.OPTIONAL,
        help="Specify a file to write the output [default=stdout]",
        default=sys.stdout,
    )

    return parser


if __name__ == '__main__':
    parser = create_parser()
    args = parser.parse_args()
    sys.exit(main(args))
