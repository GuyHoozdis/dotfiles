"""Helper function to calculate expected move for SPX.


>>> em = calc_expected_move(4347.87, 71.74)
>>> em.upper, em.close, em.lower
(4419.61, 4347.87, 4276.13)
"""
from collections import namedtuple


ExpectedMove = namedtuple('ExpectedMove', ['upper', 'close', 'lower'])


def calc_expected_move(close, delta):
    return ExpectedMove(
        upper=close+delta,
        close=close,
        lower=close-delta
    )
