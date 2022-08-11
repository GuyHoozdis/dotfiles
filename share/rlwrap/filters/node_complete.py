#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
"""
import os
import sys
import textwrap

RLWRAP_FILTERDIR = os.environ.get('RLWRAP_FILTERDIR', '.')
sys.path.append(RLWRAP_FILTERDIR)
import rlwrapfilter


def completion_handler(*args, **kwargs):
    pass



def main(args=None):
    rlwrap_filter = rlwrapfilter.RlwrapFilter()
    name = rlwrap_filter.name
    rlwrap_filter.help_text = """Usage: rlwrap -z {0} -e '' -c ~/bin/mynode.js

    Wrap the node REPL
    TODO: import textwrap to dedent this contnt
    """
    rlwrap_filter.completion_handler = completion_handler

    rlwrap_filter.run()


if __name__ == '__main__':
    sys.exit(main())
