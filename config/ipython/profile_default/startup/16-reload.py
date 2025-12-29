"""Reload a module.

Accepts a module name or a module object.

Examples:

    # Pass a module object.
    >>> from foopack import barmod
    >>> reload(barmod)

    # Pass a module name.
    >>> from foopack.barmod import bazfunc
    >>> reload('foopack.barmod')


"""
import sys

from importlib import reload as _reload
from types import ModuleType


def reload(module: ModuleType | str) -> ModuleType:
    """Reload a named module."""
    if isinstance(module, str):
        if module not in sys.modules:
            raise ValueError(f'Module {module} not found')
        module = sys.modules[module]
    return _reload(module)
