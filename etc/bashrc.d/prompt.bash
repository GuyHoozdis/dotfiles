# Everyone needs a little color in their lives

    RED='\[\033[31m\]'
    GREEN='\[\033[32m\]'
    YELLOW='\[\033[33m\]'
    BLUE='\[\033[34m\]'
    PURPLE='\[\033[35m\]'
    CYAN='\[\033[36m\]'
    WHITE='\[\033[37m\]'
    NIL='\[\033[00m\]'


# Only available on Bash 4

    PROMPT_DIRTRIM=3


# Prompt Helpers

    _get_current_branch_name_for_prompt() {
      local ACTIVE_BRANCH=$(git branch --no-color 2>/dev/null | grep '^\* ' | sed 's/^* //g')
      if [ -z ${ACTIVE_BRANCH} ]; then
        echo "Not a git repository"
      else
        echo -n ${ACTIVE_BRANCH}
      fi
    }

    _get_sourced_environment_name_for_prompt() {
      echo -n "${APP_ENVIRONMENT-System}"
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
    HOST_INFO_PROMPT="${WHITE}[${GREEN}${HOST_INFO}${WHITE}]${NIL}"

    VIRTENV_NAME="\$(pyenv version-name)"
    VIRTENV_PROMPT="${WHITE}(${CYAN}PyEnv: ${RED}${VIRTENV_NAME}${WHITE})"

    BRANCH_NAME="\$(_get_current_branch_name_for_prompt)"
    BRANCH_NAME_PROMPT="${WHITE}(${CYAN}Branch: ${RED}${BRANCH_NAME}${WHITE})${NIL}"

    APP_ENV_NAME="\$(_get_sourced_environment_name_for_prompt)"
    APP_ENV_PROMPT="${WHITE}(${CYAN}AppEnv: ${RED}${APP_ENV_NAME}${WHITE})${NIL}"

    function set_prompt() {
        PS1="\n"
        PS1+="$APP_ENV_PROMPT\n"
        PS1+="$VIRTENV_PROMPT\n"
        PS1+="$BRANCH_NAME_PROMPT\n"
        PS1+="$HOST_INFO_PROMPT\n"
        PS1+="\$ "

        export PS1
    }

    export PROMPT_COMMAND=set_prompt
