# Login shells load exports; interactive shells load shell-options, aliases,
# functions, app-config, and prompt, in that order. Each module's .local.bash
# override is sourced before its tracked .bash file.
#
# -----------------------------------------------------------------------------

# Improved `cd` command
# - Case-insensitive globbing (used in pathname expansion)
# - Correct spelling errors in arguments supplied to cd
# - Autocorrect on directory names to match a glob
# - Turn on recursive globbing (enables ** to recurse all directories)

    shopt -s nocaseglob;
    shopt -s cdspell;
    shopt -s dirspell 2> /dev/null
    shopt -s globstar 2> /dev/null

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
    HISTFILESIZE=100000
    shopt -s histappend

# Don't record certain commands

    export HISTIGNORE="&:[ ]*:exit:l[sla]::[bf]g:history:clear:pwd:pushd:popd"


# Save multi-line commands as one command
    shopt -s cmdhist
