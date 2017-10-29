#!/usr/bin/env python
"""
"""
import argparse
import json
import sys


__version__ = '0.1.0'


def create_arg_parser():
    parser = argparse.ArgumentParser(
        description='Prettify JSON',
    )
    parser.add_argument(
        'infile',
        nargs='?',
        type=argparse.FileType('r'),
        default=sys.stdin,
        help='The input file [default=stdin]',
    )
    parser.add_argument(
        'outfile',
        nargs='?',
        type=argparse.FileType('w'),
        default=sys.stdout,
        help='The output file [default=stdout]',
    )
    parser.add_argument(
        '-i', '--indent',
        type=int,
        default=2,
        help='Number of spaces to indent each level [default=%(default)s]',
    )
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s ' + __version__,
    )

    return parser


def main(infile, outfile, indention=2, separators=(',', ': ')):
    with infile:
        try:
            obj = json.load(infile)
        except ValueError, e:
            raise SystemExit(e)

    with outfile:
        json.dump(
            obj,
            outfile,
            sort_keys=True,
            indent=indention,
            separators=separators,
        )
        outfile.write('\n')


if __name__ == '__main__':
    parser = create_arg_parser()
    args = parser.parse_args()
    main(args.infile, args.outfile, args.indent)
    #sys.exit(0)
