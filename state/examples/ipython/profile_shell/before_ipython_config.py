#------------------------------------------------------------------------------
# Custom configuration
#------------------------------------------------------------------------------
c = get_config()
load_subconfig('ipython_config.py', profile='default')

c.TerminalIPythonApp.display_banner = False
c.TerminalIPythonApp.force_interact = True

import os
import subprocess
from IPython.terminal.prompts import Prompts, Token


class ShellPrompt(Prompts):

    def _prepare_current_directory_token(self, depth=None, abbrev_user=True):
        """Format the current directory for display.

        If depth is an integer greater than 0, then that value will be used
        to slice the tail elements of the current directory.

        If abbrev_user is True, the user's home directory will be abbreviated
        with a tilde.
        """
        current_directory = os.getcwd()
        user_home = os.getenv('HOME')
        if user_home and abbrev_user:
            current_directory = current_directory.replace(user_home, '~', 1)

        if depth:
            elements = current_directory.split(os.sep)[-depth:]
            current_directory = os.sep.join(elements)

        return current_directory

    def _prepare_current_branch_token(self):
        return 'TODO'

    def _prepare_current_venv_token(self):
        # Get the current virtual env name
        # XXX: If we call into a subprocess it slows down the user interaction
        #virtual_env = subprocess.check_output(
        #    ['pyenv', 'version-name']
        #).strip()
        virtual_env = 'TODO'

        return virtual_env

    def in_prompt_tokens(self, cli=None):
        directory_token = self._prepare_current_directory_token()
        branch_token = self._prepare_current_branch_token()
        venv_token = self._prepare_current_venv_token()

        return [
            (Token.Prompt, '['),
            (Token, directory_token),
            (Token.Prompt, ']'),

            (Token.Prompt, ' (Branch: '),
            (Token, branch_token),
            (Token.Prompt, ')'),

            (Token.Prompt, ' (PyEnv: '),
            (Token, venv_token),
            (Token.Prompt, ')'),

            (Token.Prompt, '\nipysh> '),
        ]


c.TerminalInteractiveShell.prompts_class = ShellPrompt