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


# Manage the components independently to be more readable.
#
# Notice the leading backslash on the command substitution below,
# where the branch name is calculated`\$(git ...`, without that
# backslash the expression is only evaluated once.

    HOSTNAME="${WHITE}[${GREEN}\w${WHITE}]${NIL}"
    VIRTENV="${WHITE}(${CYAN}PyEnv: ${RED}\$(pyenv version-name)${WHITE})"
    BRANCH="\$(git symbolic-ref --quiet --short HEAD 2>/dev/null)"
    GIT="${WHITE}(${CYAN}Branch: ${RED}${BRANCH}${WHITE})${NIL}"


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
