# Enable debugging by placing a file, with the .debug extension, next to the
# file to be examined

    DEBUG_FLAG=$HOME/.local/etc/bash_login.debug
    if [[ -f $DEBUG_FLAG ]]; then
        set -x
    fi

    function _is_interactive_shell() {
      [[ $- == *i* ]]
      return $?
    }

    function _is_login_shell() {
      shopt -q login_shell
      return $?
    }

    function _debug_info() {
      _is_interactive_shell && IS_INTERACTIVE_SHELL="IS" || IS_INTERACTIVE_SHELL="IS NOT"
      _is_login_shell && IS_LOGIN_SHELL="IS" || IS_LOGIN_SHELL="IS NOT"

      echo "Cmdline: $*"
      echo "Shell $IS_INTERACTIVE_SHELL  an interactive session"
      echo "Shell $IS_LOGIN_SHELL a login session"
      [[ -z $ITERM_PROFILE ]] && echo "ITERM_PROFILE is not set"
      [[ -z $PYTHON_ENVIRONMENT ]] && echo "PYTHON_ENVIRONMENT is not set"
  }


# ===================================================================================
# Scenarios to support
#
# 1. Default startup scenarios from ITerm, Terminal, and any explicit use of --login
# `$ bash --login`
#
# 2. Mimic the behavior of the terminal emulators, a customized command might would be
# `$ bash --rcfile ~/.bash_profile.pyenv --login`
#
# 3. Create an interactive shell with a specific configuration
# `$ bash --rcfile ~/.bash_profile.pyenv`
#
# 4. Create an interactive shell with the a default configuration
# `$ bash`
#
# 5. Non-interactive shells
#
# 6. Shells started with --noprofile or --norc
# -----------------------------------------------------------------------------------
#
#
# ===================================================================================


# Load all files from the bashrc.d directory
#
# Files with the extension .local are not committed to the repo and will be sourced
# immediately before the file of the same name without the .local extention.

    # !!!: Change this to be configurable.
    BASH_CONFIG_DIR=~/.local/etc/bashrc.d
    [[ ! -d $BASH_CONFIG_DIR ]] && return
    for filename in {exports,aliases,functions,app-config,prompt}; do
        BASH_CONFIG_FILE=${BASH_CONFIG_DIR}/${filename}
        [[ -r ${BASH_CONFIG_FILE}.local.bash ]] && source ${BASH_CONFIG_FILE}.local.bash
        [[ -r ${BASH_CONFIG_FILE}.bash ]] && source ${BASH_CONFIG_FILE}.bash
    done
