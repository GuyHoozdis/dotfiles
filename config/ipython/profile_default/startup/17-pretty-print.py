"""Utility to pretty print data structures

Some of these are aliases to match my debugging configuration.
"""
from pprint import pp

ppl = pp
ppd = pp


# TODO: Consider fetching from __slots__ too.
# !!!: The elif is not correct, as some objects have both __dict__
#      and __slots__.  This is just for reference.
#def get_from_dunder_dict(o):
#    if hasattr(o, '__dict__'):
#        return vars(o)
#    elif hasattr(o, '__slots__'):
#        return {k: getattr(o, k) for k in o.__slots__ if hasattr(o, k)}
#    return {}

def keys(o):
    mapping = {}
    if isinstance(o, dict):
        return o.keys()
    elif hasattr(o, '__dict__'):
        mapping = vars(o)

    if not mapping and hasattr(o, '__dir__'):
        mapping = {k: None for k in dir(o) if not k.startswith('_')}

    return mapping.keys()
