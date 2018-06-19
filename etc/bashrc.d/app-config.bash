
# Initialize all the completions

    [ -f $(brew --prefix)/etc/bash_completion ] && . $(brew --prefix)/etc/bash_completion


# Initialize the Python version manager

# XXX: Disabling automatically invoking pyenv, because I want to
#      try to use the new tools pipenv and hatch.  This initialization
#      will be replaced by a function.
#
    #if [[ -z $VIRTUAL_ENV ]]; then
    #  export PYENV_VIRTUALENV_DISABLE_PROMPT=1
    #  if which -s pyenv; then
    #       eval "$(pyenv init -)"
    #  else
    #      echo "Failed to initialize PyEnv"
    #  fi
    #  if which -s pyenv-virtualenv; then
    #      eval "$(pyenv virtualenv-init -)"
    #  else
    #      echo "Failed to initialize PyEnv VitualEnv"
    #  fi
    #fi

    # ???: WHY don't I just put these in the thunk itself?
    case $PYTHON_ENVIRONMENT in
      pyenv)
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
        ;;
      pipenv)
          echo "Initialize environment for $PYTHON_ENVIRONMENT"
          eval "$(pipenv --completion)"
        ;;
      *)
        echo "No python environment initialized"
        ;;
    esac


# Initialize the Ruby Version manager

    eval "$(rbenv init -)"


# Arcanist Configuration
#
# This is actually done in the .local version of this file.  It is just left here
# as an example.

    #ARCANIST_BASH_COMPLETIONS=$HOME/Development/arcanist/resources/shell/bash-completion
    #[ -f $ARCANIST_BASH_COMPLETIONS ] && . $ARCANIST_BASH_COMPLETIONS
