"""Given the cost of a debit spread, show some percentage returns.

>>> calc_in_out_spread_return(2.33)
{'30%': 3.029,
 '50%': 3.495,
 '55%': 3.61115,
 '60%': 3.728,
 '65%': 3.8445}
"""


def calc_in_out_spread_return(cost):
    percentages = {
        "30%": 1.30,
        "50%": 1.50,
        "55%": 1.55,
        "60%": 1.60,
        "65%": 1.65,
    }

    return {
        key: cost * value
        for key, value in percentages.items()
    }
