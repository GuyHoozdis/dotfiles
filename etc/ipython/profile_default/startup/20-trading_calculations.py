"""Utilities used for trading.
"""
from argparse import Namespace
from collections import namedtuple
from math import floor
from textwrap import dedent


ExpectedMove = namedtuple('ExpectedMove', 'upper close lower channel')
ChannelSettings = namedtuple('ChannelSettings', 'price height')

def __em_str__(self):
    return dedent(f"""
    ExpectedMove:
      Upper: {self.upper}
      Close: {self.close}
      Lower: {self.lower}
    Channel:
      Price:  {self.channel.price}
      Height: {self.channel.height}
    """)

ExpectedMove.__str__ = __em_str__


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
        lower=close-delta,
        channel=ChannelSettings(
            price=close-delta,
            height=delta*2,
        )
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


def calc_position_risk(equity, cost):
    """Determine the number of units of the given position to take.

    A conservative tolerance would is 2%.  An agressive tolerance is 4% or 5%.
    Anything beyond is generally considered wreckless.  These risk tolerance
    levels are designed to maximize the survivability of your account in the
    event of everything going wrong.  Taking beyond a 5% risk for any single
    position is to be wreckless.  That's gambling.  Not math.

    If the result of this function says 0 for your risk tolerance, then you
    cannot take the position.

    Args:
        equity: The total liquidated value of the account.
        cost: The debit for one unit of the position being analyzed.

    Example:
        >>> equity = 113041.66
        >>> trading_utils.position_risk(equity, 113)
        {'1%': 10, '2%': 20, '3%': 30, '4%': 40, '5%': 50}

        >>> risk_profile = trading_utils.position_risk(equity, 2_000)
        >>> risk_profile['2%']
        1
        >>> print(risk_profile)
        {'1%': 0, '2%': 1, '3%': 1, '4%': 2, '5%': 2}

        >>> risk_profile = trading_utils.position_risk(equity, 2_500)
        >>> risk_profile['2%']
        0
        >>> print(risk_profile)
        {'1%': 0, '2%': 0, '3%': 1, '4%': 1, '5%': 2}

    """
    def _risk(tolerance):
        return floor((_D(equity) * _D(tolerance)) / _D(cost))

    percentages = {
        "1%": _D(.01),
        "2%": _D(.02),
        "3%": _D(.03),
        "4%": _D(.04),
        "5%": _D(.05),
    }
    return {
        key: _risk(value)
        for key, value in percentages.items()
    }


# #############################################################################
# I want to make it easier to find these utilities instead of trying to recall
# the name.
# #############################################################################

# Idea 1) Package them as a namespace.
# - The Namespace is convoluted when you do things like '?' or '??' on the
#   object.
# - Maybe it would be better / cleaner if I just wrapped them in a class
#   defined here.
trading_utils_ns = Namespace(
    expected_move=calc_expected_move,
    vertical_spread_return=calc_in_out_spread_return,
    position_risk=calc_position_risk,
    __doc__="Simulate a module for trading utilties",
)
# -----------------------------------------------------------------------------

# Idea 2) Package them as module.
# - This works and behaves correctly for things like '?' and '??'.
# - It needs to be imported once in the shell though.  Not sure if that is a
#   good or bad thing, but it is different from how other startup scripts work.
# - Maybe it would make more sense to make this an actual package / module and
#   then this startup script could import it.
import sys
from types import ModuleType
_trading_utils_module = ModuleType("trading_utils")
sys.modules[_trading_utils_module.__name__] = _trading_utils_module
_trading_utils_module.__file__ = __file__
_trading_utils_module.__doc__ = __doc__

_trading_utils_module.expected_move = calc_expected_move
_trading_utils_module.vertical_spread_return = calc_in_out_spread_return
_trading_utils_module.position_risk = calc_position_risk

# !!!: I added a startup script that loads immediately after this one and does
# the import <module>.  That seems to have worked, but it seems like a lot to
# do to avoid making a real module / package.
# -----------------------------------------------------------------------------
