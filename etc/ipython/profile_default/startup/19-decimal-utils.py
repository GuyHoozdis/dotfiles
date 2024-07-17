"""Utilities to extend the decimal package.
"""
from decimal import Decimal


def to_decimal(value='0', context=None):
    """Wrap numerical values as a string before passing to Decimal.
    """
    return Decimal(str(value), context=context)


# This is supposed to be like how I used to handle strings
# in C/C++ on Win32 systems - the macro.  Maybe that is
# a bad idea because in Python the '_' has special meaning.
_D = to_decimal
