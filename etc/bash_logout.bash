# Enable debugging by placing a file, with the .debug extension, next to the
# file to be examined

    DEBUG_FLAG=$HOME/.local/etc/bash_logout.debug
    if [[ -f $DEBUG_FLAG ]]; then
        set -x
    fi


# This file will be invoked when an interactive login shell is terminated.
