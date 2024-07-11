"""Utilities used for trading.
"""
from collections import namedtuple
from decimal import Decimal


ExpectedMove = namedtuple('ExpectedMove', ['upper', 'close', 'lower'])


def to_decimal(value):
    """Wrap numerical values as a string before passing to Decimal.
    """
    return Decimal(str(value))

_D = to_decimal


def calc_expected_move(close, delta):
    """Helper function to calculate expected move.

    Parameters are read from the option chain for a given underlying.

    Args:
        close: The central point, generally taken from the last print or close.
        detla: The projected variance.

    Example:
        >>> em = calc_expected_move(4347.87, 71.74)
        >>> em.upper, em.close, em.lower
        (4419.61, 4347.87, 4276.13)
    """
    close = _D(close)
    delta = _D(delta)

    return ExpectedMove(
        upper=close+delta,
        close=close,
        lower=close-delta
    )


def calc_in_out_spread_return(cost):
    """Given the cost of a debit spread, show some percentage returns.

    Args:
        cost: The debit for one spread.

    Example:
        >>> calc_in_out_spread_return(2.33)
        {'30%': 3.029,
         '50%': 3.495,
         '55%': 3.61115,
         '60%': 3.728,
         '65%': 3.8445}
    """
    percentages = {
        "30%": _D(1.30),
        "50%": _D(1.50),
        "55%": _D(1.55),
        "60%": _D(1.60),
        "65%": _D(1.65),
    }

    cost = _D(cost)
    return {
        key: cost * value
        for key, value in percentages.items()
    }
