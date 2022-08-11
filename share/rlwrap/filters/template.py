#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""<% short_description %>

Usage: rlwrap -z '<% filter %> <% filter_args %>' <% wrapped_command %>

<% full_description %>

Run the tests in this filter module with the following command:

    $ ./<% filter %> --doctest-rlwrap-filter
"""
import os
import sys
import textwrap

RLWRAP_FILTERDIR = os.environ.get('RLWRAP_FILTERDIR', '.')
sys.path.append(RLWRAP_FILTERDIR)
try:
    from rlwrapfilter import RlwrapFilter
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        "The rlwrapfilter.py module is not on your search path.  It is a part "
        "of the source code installed with the rlwrap package."
    )


#
# Handlers
#
def template_handler(*args, **kwargs):
    """Short description about this handler

    More information about this handler.  You'll probably want to change the
    name of this method from "template_" to something more appropriate.  The
    method signature can be specialized too.

    Finally, you will want to customize some tests specific to this handler.

    >>> template_handler(42, foo='bar') is None
    True
    """
    pass


#
# Bootstrap / Internal Utilities
#
def create_filter():
    """Instantiate a filter instance and configure its help text.

    >>> create_filter() is not None
    True
    >>> isinstance(create_filter(), RLwrapFilter)
    True
    >>> rlwrap_filter = create_filter()
    >>> rlwrap_filter.help_text is not None
    True
    """
    rlwrap_filter = RlwrapFilter()
    short_description, _, usage = __doc__[:3]
    rlwrap_filter.help_text = textwrap.dedent("""
        {usage}

        {description}
        """.format(usage=usage, description=short_description)
    ).strip()

    return rlwrap_filter


def create_filter_argument_parser():
    """Filter modules can have their own arguments. """
    parser = argparse.ArgumentParser()
    # TODO: Define argument
    #
    # parser.add_argument(...

    return parser


def test():
    """Simple test runner for this module"""
    import doctest

    failed, passed = doctest.testmod()
    format_report_line = "{} tests {}".format
    print(format_report_line(passed, "passed"))
    print(format_report_line(failed, "failed"))

    return failed


#
# Entry Points
#
def main(args=None):
    """Configure and run the <% filter_name %> filter"""
    rlwrap_filter = create_filter()

    # TODO: Configure your filter by assigning methods to the hooks exposed by
    #       the RlwrapFilter interface.
    #
    # rlwrap_filter.completion_handler = completion_handler
    # rlwrap_filter.completion_handler = completion_handler
    # rlwrap_filter.completion_handler = completion_handler

    rlwrap_filter.run()


if __name__ == '__main__':
    if '--doctest-rlwrap-filter' in sys.argv:
        sys.exit(test())
    sys.exit(main())
