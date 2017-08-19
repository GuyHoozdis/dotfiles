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


# Git Prompt Helper

    _git_current_branch_for_prompt() {
      local ACTIVE_BRANCH=$(git branch --no-color 2>/dev/null | grep '^\* ' | sed 's/^* //g')
      if [ -z ${ACTIVE_BRANCH} ]; then
        echo "Not a git repository"
      else
        echo -n ${ACTIVE_BRANCH}
      fi
    }


# Manage the components independently to be more readable.
#
# Notice the leading backslash on the command substitution below,
# where the branch name is calculated`\$(git ...`, without that
# backslash the expression is only evaluated once.

    HOSTNAME="${WHITE}[${GREEN}\w${WHITE}]${NIL}"
    VIRTENV="${WHITE}(${CYAN}PyEnv: ${RED}\$(pyenv version-name)${WHITE})"
    BRANCH="\$(_git_current_branch_for_prompt)"
    GIT="${WHITE}(${CYAN}Branch: ${RED}${BRANCH}${WHITE})${NIL}"
    # XXX: If you want to add this to the prompt, you need to evaluate the variable
    # everytime (like $BRANCH) not just when this file is sourced.
    #APP_ENV="${WHITE}(${CYAN}AppEnv: ${RED} ${APP_ENVIRONMENT-System}${WHITE})${NIL}"


# Put it together and what have you gut!?!  Something that is not
# very good looking... but it is functional.  Meh, I've been running
# with no color in my prompt for the last year and a half and this is
# incrementally better than that.  I think I'm going to look seriously
# at powerline/airline again.

    function set_prompt() {
        PS1="\n"
        PS1+="$HOSTNAME\n"
        PS1+="$GIT $VIRTENV\n"
        PS1+="\$ "

        export PS1
    }
    export PROMPT_COMMAND=set_prompt
