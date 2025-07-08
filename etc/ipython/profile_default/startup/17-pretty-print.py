"""Utility to pretty print data structures

Some of these are aliases to match my debugging configuration.
"""
from pprint import pp

ppl = pp
ppd = pp


def keys(o):
    if isinstance(o, dict):
        return o.keys()
    elif hasattr(o, '__dict__'):
        return vars(o).keys()
    raise TypeError(f"You haven't yet defined how to do this for type {type(o)}.")

