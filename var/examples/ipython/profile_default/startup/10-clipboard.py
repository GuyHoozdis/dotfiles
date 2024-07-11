"""Write content from the iPython shell onto the clipboard.

>>> foo = "bar baz"
>>> %pbcopy foo
>>> !pbpaste
bar baz

>>> %pbcopy
... This content
... will be written
... too!
...
"""
from __future__ import absolute_import
from __future__ import print_function

import subprocess
import sys

from functools import partial
from IPython.core.magic import register_line_cell_magic


pipe_stdin_to_process = partial(
    subprocess.Popen,
    env={'LANG': 'en_US.UTF-8'},
    stdin=subprocess.PIPE
)


def _copy_to_clipboard(content):
    content = str(globals().get(content) or content)
    process = pipe_stdin_to_process('pbcopy')
    process.communicate(content.encode('utf-8'))
    print('Copied to PasteBoard')


@register_line_cell_magic
def pbcopy(line, cell=None):
    """Are you my docstring?
    """
    cell = '\n'.join((line, cell)) if line and cell else None
    _copy_to_clipboard(cell or line)


del pbcopy
