# General System Configuration
##############################

    export LANG=en_US.UTF-8
    export LC_ALL=en_US.UTF-8

# Improved `cd` command
# - Case-insensitive globbing (used in pathname expansion)
# - Correct spelling errors in arguments supplied to cd
# - Autocorrect on directory names to match a glob
# - Turn on recursive globbing (enables ** to recurse all directories)

    shopt -s nocaseglob;
    shopt -s cdspell;
    shopt -s dirspell 2> /dev/null
    shopt -s globstar 2> /dev/null


# Enhance application search path

    NODE_MODULES_BIN=$HOME/node_modules/.bin
    PERSONAL_BIN=$HOME/.local/bin
    [[ -d $PYENV_BIN ]] && PATH=$PYENV_BIN:$PATH
    [[ -d $NODE_MODULES_BIN ]] && PATH=$NODE_MODULES_BIN:$PATH
    [[ -d $PERSONAL_BIN ]] && PATH=$PERSONAL_BIN:$PATH
    export PATH


# V-I'm in love with your key bindings

    export EDITOR=/usr/bin/vim


# Customize History
###################

# Enable history expansion with space (e.g. typing !!<space> will expand
# into your last command).

    bind Space:magic-space


# Use standard ISO 8601 timestamp
# - %F equivalent to %Y-%m-%d
# - %T equivalent to %H:%M:%S (24-hours format)

    export HISTTIMEFORMAT='%F %T '


# Keep history up-to-date, across sessions, in realtime
#  http://unix.stackexchange.com/a/48113
#
# - No duplicate entries
# - Large history (default is 500) and file size
# - Append to history, don't overwrite it

    HISTCONTROL="erasedups:ignoreboth"
    HISTSIZE=100000
    HISTFILESIZE=10000
    shopt -s histappend

# Don't record certain commands

    export HISTIGNORE="&:[ ]*:exit:ls:bg:fg:history:clear"


# Save multi-line commands as one command
    shopt -s cmdhist

# - Save and reload the history after each comand
#
# !!!: Keep an eye on this, it may not work as expected.
#  https://stackoverflow.com/questions/338285/prevent-duplicates-from-being-saved-in-bash-history#answer-7449399

    export PROMPT_COMMAND="history -a; history -c; history -r; $PROMPT_COMMAND"


