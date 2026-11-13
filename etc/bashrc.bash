# Per-shell initialization: functions, aliases, completions, and the prompt.
#
# Bash reads this file for interactive non-login shells; ~/.bash_profile sources
# it for login shells. It deliberately leaves PATH and other exported environment
# alone so a child shell keeps what it inherited (see decision 0007).

    [[ $- == *i* ]] || return

# Files with the extension .local are not committed to the repo and will be sourced
# immediately before the file of the same name without the .local extention.

    BASH_CONFIG_DIR="$HOME/.local/etc/bashrc.d"
    if [[ -d $BASH_CONFIG_DIR ]]; then
        for filename in {shell-options,aliases,functions,app-config,prompt}; do
            BASH_CONFIG_FILE=${BASH_CONFIG_DIR}/${filename}
            [[ -r ${BASH_CONFIG_FILE}.local.bash ]] && source "${BASH_CONFIG_FILE}.local.bash"
            [[ -r ${BASH_CONFIG_FILE}.bash ]] && source "${BASH_CONFIG_FILE}.bash"
        done
    fi
