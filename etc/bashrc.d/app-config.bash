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

    # TODO: Test if rbenv is installed first.
    eval "$(rbenv init -)"


# Arcanist Configuration
#
# This is actually done in the .local version of this file.  It is just left here
# as an example.

    #ARCANIST_BASH_COMPLETIONS=$HOME/Development/arcanist/resources/shell/bash-completion
    #[ -f $ARCANIST_BASH_COMPLETIONS ] && . $ARCANIST_BASH_COMPLETIONS
