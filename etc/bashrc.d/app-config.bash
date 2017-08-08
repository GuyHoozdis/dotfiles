
# Initialize all the completions

    [ -f $(brew --prefix)/etc/bash_completion ] && . $(brew --prefix)/etc/bash_completion


# Initialize the Python version manager

    export PYENV_VIRTUALENV_DISABLE_PROMPT=1
    if which -s pyenv; then
         eval "$(pyenv init -)"
    else
        echo "Failed to initialize PyEnv"
    fi
    if which -s pyenv-virtualenv; then
        eval "$(pyenv virtualenv-init -)"
    else
        echo "Failed to initialize PyEnv VitualEnv"
    fi


# Arcanist Configuration
#
# This is actually done in the .local version of this file.  It is just left here
# as an example.

    #ARCANIST_BASH_COMPLETIONS=$HOME/Development/arcanist/resources/shell/bash-completion
    #[ -f $ARCANIST_BASH_COMPLETIONS ] && . $ARCANIST_BASH_COMPLETIONS
