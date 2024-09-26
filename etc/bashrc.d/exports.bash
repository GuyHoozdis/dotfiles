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

# Export Homebrew Environment
# - On Apple Silicon Homebrew installs under `/opt/homebrew` instead of `/usr/local` (it does this to
#   avoid requiring `sudo` and/or requiring `chmod -R <foo>:<bar> /usr/local`).
# - If `brew` isn't configured when things like `pyenv` or `gls` are used or even tested if they are
#   installed, then things won't work as expected.
# - That is why this has to be done pretty early on.

  function initialize_homebrew() {
    local path_suffix=bin/brew
    if [ -x /usr/local/${path_suffix} ]; then
      eval "$(/usr/local/${path_suffix} shellenv)"
    elif [ -x /opt/homebrew/$path_suffix ]; then
      eval "$(/opt/homebrew/${path_suffix} shellenv)"
    fi
  }

  initialize_homebrew && echo "Homebrew initialized" || echo "Homebrew not installed"


# Enhance application search path

  # Enabling/disabling shell configurations based on envvars
  # 1. Disable the variations and create the entrypoints
  # 2. Verify each detects the appropriate signal
  # 3. Enable the path that replicates the environment that has previously been used
  # 5. Profit

# Initialize the Python version manager

    # If pyenv is installed and hasn't been initialized yet.
    if which -s pyenv && [[ -z "${PYENV_SHELL}" ]]; then
      export PYENV_VIRTUALENV_DISABLE_PROMPT=1
      eval "$(pyenv init -)"
    fi

# Initialize the Ruby Version manager

    # If rbenv is installed and hasn't been initialized yet.
    if which -s rbenv && [[ -z "${RBENV_SHELL}" ]]; then
      eval "$(rbenv init -)"
    fi

# Put my personal executables after pyenv and rbenv so that my custom executables
# and pipx executables are located before any shims.
    function exists_in_path () {
      target=$1
      echo -e ${PATH//:/\\n} | egrep "^${target}$" &>/dev/null
      return $?
    }

    NODE_MODULES_BIN=$HOME/node_modules/.bin
    PERSONAL_BIN=$HOME/.local/bin
    if ! exists_in_path $NODE_MODULES_BIN; then
      [[ -d $NODE_MODULES_BIN ]] && PATH=$NODE_MODULES_BIN:$PATH
    fi
    if ! exists_in_path $PERSONAL_BIN; then
      [[ -d $PERSONAL_BIN ]] && PATH=$PERSONAL_BIN:$PATH
    fi
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

    # XXX: Disabling until I review and install rlwrap again.
    #export RLWRAP_HOME=$HOME/.rlwrap
    #export RLWRAP_EDITOR="vi '+call cursor(%L, %C)'"
    ##export RLWRAP_FILTERDIR=/usr/local/share/rlwrap/filters
    #export RLWRAP_FILTERDIR=$HOME/.local/share/rlwrap/filters


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
