# The exports are sourced before this, so those values are available
# to be used in this module.  In pseudo code; the load order goes
# like this:
#
#   for filename in {exports,aliases,functions,app-config,prompt};
#     load filename.local.bash if filename.local.bash exists;
#     load filename.bash if filename.bash exists;
#
# -----------------------------------------------------------------------------

# This is to support scenarios where the subshell is passed
# `PROMPT_COMMAND`, but then can't access `set_prompt` nor
# any of the functions is relies upon.
#
#   https://stackoverflow.com/a/28490273
#
# Actually, this sucks... it really messes up the output of the `env` command.
    #set -a


# Everyone needs a little color in their lives

    #RED='\[\033[31m\]'
    #GREEN='\[\033[32m\]'
    #YELLOW='\[\033[33m\]'
    #BLUE='\[\033[34m\]'
    #PURPLE='\[\033[35m\]'
    #CYAN='\[\033[36m\]'
    #WHITE='\[\033[37m\]'
    #NIL='\[\033[00m\]'

    RED='\[\e[31m\]'
    GREEN='\[\e[32m\]'
    YELLOW='\[\e[33m\]'
    BLUE='\[\e[34m\]'
    PURPLE='\[\e[35m\]'
    CYAN='\[\e[36m\]'
    WHITE='\[\e[37m\]'
    CLEAR='\[\e[00m\]'
    NIL='\[\e[00m\]'


# Only available on Bash 4

    PROMPT_DIRTRIM=3


# Prompt Helpers
#
# TODO:
# - The switch `-v` just wasn't working the way I was using it.  Using `-n` does have the
#   advantage of being supported on older versions of bash.  I would otherwise have to
#   introduce version specific logic.  :/
# - I believe `-n` is the default switch, so `[[ -n $SOME_VAR ]]` can be reduced to
#   simply `[[ $SOME_VAR ]]`.
# - In addition to the simplification mentioned above, it looks like a few of these
#   statements could be cleaned up to be a little tighter.

    _is_pyenv_active() {
      [[ -n $PYENV_ACTIVE ]] && return 0
      [[ -n $PYENV_SHELL ]] && return 0
      [[ -n $PYENV_VIRTUALENV_INIT ]] && return 0
      return 1
    }

    _is_standard_virtualenv_active() {
      [[ -n $VIRTUAL_ENV ]] && return 0 || return 1
    }

    _get_current_branch_name_for_prompt() {
      local branch=$(git branch --no-color 2> /dev/null | grep '^\* ')
      [[ -z "${branch}" ]] && branch="ThisValueNotShown Not a git repository"
      echo -n "${branch#* }"
    }

    _get_sourced_environment_name_for_prompt() {
      local profile="${ITERM_PROFILE:-${PYTHON_ENVIRONMENT:-Unknown}}"
      local level=${SHLVL-Err}
      if [[ -z $APP_ENVIRONMENT ]]; then
        echo -n "System ($profile)[$level]"
      else
        echo -n "$APP_ENVIRONMENT ($profile)[$level]"
      fi
    }

    _get_sourced_docker_machine_name_for_prompt() {
      local machine_name=${DOCKER_MACHINE_NAME-System}
      printf "${DOCKER_MACHINE_NAME-System}" \
        && [[ -n $COMPOSE_FILE ]] \
        && printf " (%s)" $COMPOSE_FILE
      printf "\n"
    }

    _get_current_venv_name_for_prompt() {
      if _is_standard_virtualenv_active; then
        venv=$(basename "${VIRTUAL_ENV}"); echo -n "${venv}"
      elif _is_pyenv_active; then
        venv=$(pyenv version-name); echo -n "${venv//:/|}"
      else
        local python_binary="Not Installed"
        if which -s python; then
          python_binary=$(greadlink $(which python))
        fi

        if [[ $python_binary = /usr/local/bin/python* ]]; then
          echo -n "Brewed $(basename $python_binary)"
        elif [[ $python_binary = /usr/bin/python* ]]; then
          echo -n "System $(basename $python_binary)"
        else
          echo -n "$python_binary"
        fi
      fi
    }

    _get_colored_venv_label() {
      if _is_standard_virtualenv_active; then
        #venv=$(basename "${VIRTUAL_ENV}"); echo -n "${venv}"
        echo -n '${WHITE}ViEnv${NIL}'
      elif _is_pyenv_active; then
        #venv=$(pyenv version-name); echo -n "${venv//:/|}"
        echo -n '${CYAN}PyEnv${NIL}'
      else
        echo -n '${GREEN}SysEnv${NIL}'
      fi
    }

    _get_venv_label() {
      if _is_standard_virtualenv_active; then
        echo -n 'ViEnv'
      elif _is_pyenv_active; then
        echo -n 'PyEnv'
      else
        echo -n 'SysEnv'
      fi
    }



# Manage the components independently to be more readable.
#
# Notice the leading backslash on the command substitution below,
# where the branch name is calculated`\$(git ...`, without that
# backslash the expression is only evaluated once.
#
# TODO: Wishlist
#  * I'd like to change the color or styling of elements based on attributes of
#    that element; for example, the git branch can be red (or underlined) when it
#    has changes and green otherwise.
#  * Right now I have the elements stacked, which is fine when I'm on big screens, but
#    I'd like to be able to collapse or toggle the elements easily and as needed.

    HOST_INFO="\w"
    HOST_INFO_PROMPT="${BLUE}[${GREEN}${HOST_INFO}${BLUE}]${NIL}"

    BRANCH_NAME="\$(_get_current_branch_name_for_prompt)"
    BRANCH_NAME_PROMPT="${BLUE}(${WHITE}Branch : ${PURPLE}${BRANCH_NAME}${BLUE})${NIL}"
    BRANCH_NAME_PROMPT_GIT="${BLUE}(${WHITE}Branch${NIL} : %s${BLUE})${NIL}"

    APP_ENV_NAME="\$(_get_sourced_environment_name_for_prompt)"
    APP_ENV_PROMPT="${BLUE}(${WHITE}AppEnv : ${PURPLE}${APP_ENV_NAME}${BLUE})${NIL}"

    DOCKER_SWARM_NAME="\$(_get_sourced_docker_machine_name_for_prompt)"
    DOCKER_SWARM_PROMPT="${BLUE}(${WHITE}Docker : ${PURPLE}${DOCKER_SWARM_NAME}${BLUE})${NIL}"

    VIRTENV_NAME="\$(_get_current_venv_name_for_prompt)"
    if _is_standard_virtualenv_active; then
        ####  Using Hatch and VirtualEnv Dev Environment #####
        #VIRTENV_PROMPT="${BLUE}(${WHITE}ViEnv  : ${PURPLE}${VIRTENV_NAME}${BLUE})${NIL}"
        #VIRTENV_PROMPT="${BLUE}(${NIL}\$(_get_colored_venv_label)  : ${PURPLE}${VIRTENV_NAME}${BLUE})${NIL}"
        VIRTENV_PROMPT="${BLUE}(${GREEN}\$(_get_venv_label)  : ${PURPLE}${VIRTENV_NAME}${BLUE})${NIL}"
    elif _is_pyenv_active; then
        ####  Normal Environment
        #VIRTENV_PROMPT="${BLUE}(${CYAN}PyEnv  : ${RED}${VIRTENV_NAME}${WHITE})${NIL}"
        #VIRTENV_PROMPT="${BLUE}(${NIL}\$(_get_colored_venv_label)  : ${RED}${VIRTENV_NAME}${WHITE})${NIL}"
        VIRTENV_PROMPT="${BLUE}(${WHITE}\$(_get_venv_label)  : ${RED}${VIRTENV_NAME}${BLUE})${NIL}"
    else
        #VIRTENV_PROMPT="${BLUE}(${RED}NoVenv : ${CYAN}${VIRTENV_NAME}${WHITE})${NIL}"
        #VIRTENV_PROMPT="${BLUE}(${NIL}\$(_get_colored_venv_label) : ${CYAN}${VIRTENV_NAME}${WHITE})${NIL}"
        VIRTENV_PROMPT="${BLUE}(${RED}\$(_get_venv_label) : ${CYAN}${VIRTENV_NAME}${BLUE})${NIL}"
    fi

    # ==============================================================================
    # See `/usr/local/opt/git/etc/bash_completion.d/git-prompt.sh` for
    # descriptions of the following variables.
    #
    GIT_PS1_SHOWDIRTYSTATE=true
    # GIT_PS1_SHOWSTASHSTATE=true
    GIT_PS1_SHOWUNTRACKEDFILES=true
    GIT_PS1_SHOWUPSTREAM=auto
    GIT_PS1_STATESEPARATOR="|"
    GIT_PS1_DESCRIBE_STYLE=branch
    GIT_PS1_SHOWCOLORHINTS=true
    # GIT_PS1_HIDE_IF_PWD_IGNORED
    # ==============================================================================

    function set_prompt() {
      if ! type -t __git_ps1 >/dev/null; then
        # !!!: Leaving this in case I want to turn it on again, so I can see the 
        # scenarios where this happens.
        #echo "Repairing missing __git_ps1"
        local filepath_suffix=opt/git/etc/bash_completion.d/git-prompt.sh
        if [ -f /usr/local/$filepath_suffix ]; then
          . /usr/local/$filepath_suffix
        elif [ -f /opt/homebrew/$filepath_suffix ]; then
          . /opt/homebrew/$filepath_suffix
        fi
      fi
      __git_ps1 "\n$APP_ENV_PROMPT \n$DOCKER_SWARM_PROMPT \n$VIRTENV_PROMPT" "\n$HOST_INFO_PROMPT \n\$ " "\n$BRANCH_NAME_PROMPT_GIT"
    }

    # Turns out I don't like how this is working in practice.  If I've transitioned back from another terminal and want to execute the previous
    # command, now I have to scroll past several commands (from other terminals/sessions) to get the last command executed in this terminal. I
    # will have to think about this some more.
    #export PROMPT_COMMAND="history -a; history -c; history -r; set_prompt"

    #
    export PROMPT_COMMAND=set_prompt

    unset RED
    unset GREEN
    unset YELLOW
    unset BLUE
    unset PURPLE
    unset CYAN
    unset WHITE
    unset NIL
    unset CLEAR


# Revert to normal
    #set +a
