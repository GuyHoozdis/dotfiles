# Enable debugging by placing a file, with the .debug extension, next to the
# file to be examined

    DEBUG_FLAG=$HOME/.local/etc/bash_login.debug
    if [[ -f $DEBUG_FLAG ]]; then
        set -x
    fi

# Load all files from the bashrc.d directory
#
# Files with the extension .local are not committed to the repo and will be sourced
# immediately before the file of the same name without the .local extention.

    BASH_CONFIG_DIR=~/.local/etc/bashrc.d
    [[ ! -d $BASH_CONFIG_DIR ]] && return
    for filename in {exports,aliases,functions,app-config,prompt}; do
        BASH_CONFIG_FILE=${BASH_CONFIG_DIR}/${filename}
        [[ -r ${BASH_CONFIG_FILE}.local.bash ]] && source ${BASH_CONFIG_FILE}.local.bash
        [[ -r ${BASH_CONFIG_FILE}.bash ]] && source ${BASH_CONFIG_FILE}.bash
    done
    unset filename