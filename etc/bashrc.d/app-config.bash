# Login shells load exports; interactive shells load shell-options, aliases,
# functions, app-config, and prompt, in that order. Each module's .local.bash
# override is sourced before its tracked .bash file.
#
# -----------------------------------------------------------------------------

# Initialize all the completions

    command -v brew >/dev/null 2>&1 \
      && [ -f "$(brew --prefix)/etc/profile.d/bash_completion.sh" ] \
      && . "$(brew --prefix)/etc/profile.d/bash_completion.sh"


# ##############################################################################
# !!!: Since I recently started using pipx, it is installing things into ~/.local/bin, but
# when there is a thing (e.g. poetry, keyring, nox, ...) that exists both in a pyenv managed
# environment and the pipx bin directory, then the pix utility isn't found because the PATH
# has the pipx bin directory comes after the pyenv and rbenv shims.
#
# For now I'm going to try moving these operations into the exports directory so that I can
# control the order in which they go onto the path.
# ##############################################################################

# Initialize the Python version manager
#
#    # If pyenv is installed and hasn't been initialized yet.
#    if which -s pyenv && [[ -z "${PYENV_SHELL}" ]]; then
#      export PYENV_VIRTUALENV_DISABLE_PROMPT=1
#      eval "$(pyenv init -)"
#    fi

# Initialize the Ruby Version manager
#
#    # If rbenv is installed and hasn't been initialized yet.
#    if which -s rbenv && [[ -z "${RBENV_SHELL}" ]]; then
#      eval "$(rbenv init -)"
#    fi
# ##############################################################################

# Arcanist Configuration
#
# This is actually done in the .local version of this file.  It is just left here
# as an example.

    #ARCANIST_BASH_COMPLETIONS=$HOME/Development/arcanist/resources/shell/bash-completion
    #[ -f $ARCANIST_BASH_COMPLETIONS ] && . $ARCANIST_BASH_COMPLETIONS
