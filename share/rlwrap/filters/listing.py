#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A port of rlwrap's listing filter.

> This filter is only used to get a list of filters via 'rlwrap -z listing
> It is not usable as a filter (and would do nothing useful)

 See https://github.com/hanslub42/rlwrap/blob/v0.43/filters/listing
"""
import os
import sys

from glob import glob

RLWRAP_LIB='/usr/local/share/rlwrap/filters'
RLWRAP_FILTERDIR = os.environ.get('RLWRAP_FILTERDIR', os.path.abspath('.'))
sys.path.append(RLWRAP_LIB)
sys.path.append(RLWRAP_FILTERDIR)

from rlwrapfilter import RlwrapFilter

import subprocess
def get_info(filename):
    os.environ.pop('RLWRAP_COMMAND_PID', None)
    p1 = subprocess.Popen(
        ['cat'],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
    )
    p2 = subprocess.Popen(
        [filename],
        stdin=p1.stdout,
        stderr=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
    )
    p1.stdout.close()
    #import ipdb; ipdb.sset_trace();  # Breakpoint
    try:
        out, err = p2.communicate(timeout=1)
    except subprocess.TimeoutExpired:
        p2.kill()
        out, err = p2.communicate()
    return out
    #import ipdb; ipdb.sset_trace();  # Breakpoint
    #trash = out.readline()
    #info = out.readline()
    #moretrash = out.readlines()
    #return info

    #with open(filename) as istream:
    #    istream.readline()          # Throw away 1st line
    #    info = istream.readline()   # Capture the second
    #    istream.readlines()         # :shruggie:
    #return info


def main(args=None):
    rlwrap_filter = RlwrapFilter()
    name = rlwrap_filter.name
    command_line = rlwrap_filter.command_line
    if command_line:
        sys.stderr.write(
            "This filter is only used to get a list of filters via "
            "'rlwrap -z listing'\nIt is not usable as a filter (and would do "
            "nothing useful)\n\n"
        )
        sys.stderr.flush()
        return 1

    msg = "The following filters can be found in {}".format(RLWRAP_FILTERDIR)
    rlwrap_filter.send_output_oob(msg)
    filter_files = glob(RLWRAP_FILTERDIR + '/*')
    for filter_file in (f for f in filter_files if os.path.isfile(f)):
        if filter_file.endswith(name):
            continue

        info = get_info(filter_file)
        if not info:
            continue

        format_line = "{0:{width}.{precision}} {1}".format
        filename = os.path.basename(filter_file)
        rlwrap_filter.send_output_oob(
            format_line(filename, info, width=30, precision=30)
        )

    rlwrap_filter.run()


if __name__ == '__main__':
    sys.exit(main())
