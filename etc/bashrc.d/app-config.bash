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


# Initialize the Python version manager

    if which -s pyenv; then
      export PYENV_VIRTUALENV_DISABLE_PROMPT=1
      eval "$(pyenv init -)"
    fi


# Initialize the Ruby Version manager

    if which -s rbenv; then
      eval "$(rbenv init -)"
    fi


# Arcanist Configuration
#
# This is actually done in the .local version of this file.  It is just left here
# as an example.

    #ARCANIST_BASH_COMPLETIONS=$HOME/Development/arcanist/resources/shell/bash-completion
    #[ -f $ARCANIST_BASH_COMPLETIONS ] && . $ARCANIST_BASH_COMPLETIONS
