# The exports are sourced before this, so those values are available
# to be used in this module.  In pseudo code; the load order goes
# like this:
#
#   for filename in {exports,aliases,functions,app-config,prompt};
#     load filename.local.bash if filename.local.bash exists;
#     load filename.bash if filename.bash exists;
#
# -----------------------------------------------------------------------------

# Initialize all the completions

    [ -f $(brew --prefix)/etc/bash_completion ] && . $(brew --prefix)/etc/bash_completion


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
