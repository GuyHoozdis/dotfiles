# This is the first module to be sourced.  In pseudo code; the load order goes
# like this:
#
#   for filename in {exports,aliases,functions,app-config,prompt};
#     load filename.local.bash if filename.local.bash exists;
#     load filename.bash if filename.bash exists;
#
# -----------------------------------------------------------------------------

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

  # Enabling/disabling shell configurations based on envvars
  # 1. Disable the variations and create the entrypoints
  # 2. Verify each detects the appropriate signal
  # 3. Enable the path that replicates the environment that has previously been used
  # 4. Enable the path that allows for PipEnv and Hatch!
  # 5. Profit

    #PIPENV_BIN=$HOME/.pipenv/bin
    #PYENV_BIN=$HOME/.pyenv/bin
    #[[ -d $PIPENV_BIN ]] && PATH=$PIPENV_BIN:$PATH
    #[[ $(/usr/bin/which -s pyenv) ]] && [[ -d $PYENV_BIN ]] && PATH=$PYENV_BIN:$PATH

    NODE_MODULES_BIN=$HOME/node_modules/.bin
    PERSONAL_BIN=$HOME/.local/bin
    PERSONAL_PYTHON_BIN=$HOME/Library/Python/3.6/bin
    [[ -z $(/usr/bin/which -s node) ]] && [[ -d $NODE_MODULES_BIN ]] && PATH=$NODE_MODULES_BIN:$PATH
    [[ -d $PERSONAL_BIN ]] && PATH=$PERSONAL_BIN:$PATH
    [[ -d $PERSONAL_PYTHON_BIN ]] && PATH=$PERSONAL_PYTHON_BIN:$PATH
    export PATH


# V-I'm in love with your key bindings
# - rlwrap is a utility to bring the readline behavior to
#   utilities that do not support it natively.
# - See rlwrap's man pages for more info on the env vars below.
# - RLWRAP_FILTERDIR points to where my filters reside.  My filters in turn
#   use rlwrapfilter.py which resides in /usr/local/shared/rlwrap/filters/
#   which is a symbolic link into the current version of rlwrap installed via
#   Homebrew. Pointing RLWRAP_FILTERDIR there or putting my filters in that
#   directory would mean things break when brew upgrades rlwrap.

    [[ -e /usr/local/bin/vi ]] \
      && export EDITOR=/usr/local/bin/vi \
      || export EDITOR=/usr/bin/vi
    export RLWRAP_HOME=$HOME/.rlwrap
    export RLWRAP_EDITOR="vi '+call cursor(%L, %C)'"
    #export RLWRAP_FILTERDIR=/usr/local/share/rlwrap/filters
    export RLWRAP_FILTERDIR=$HOME/.local/share/rlwrap/filters


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

    export HISTIGNORE="&:[ ]*:exit:ls:ll:bg:fg:history:clear"


# Save multi-line commands as one command
    shopt -s cmdhist

# - Save and reload the history after each comand
#
# !!!: Keep an eye on this, it may not work as expected.
#  https://stackoverflow.com/questions/338285/prevent-duplicates-from-being-saved-in-bash-history#answer-7449399
#
# Note moving this functionality into `prompt.bash`, which comes later in the
# config process.  I this this has been overwritten by an assignment to the
# same variable there.
#
#    export PROMPT_COMMAND="history -a; history -c; history -r; $PROMPT_COMMAND"


