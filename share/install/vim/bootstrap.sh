#!/usr/bin/env bash


# These values can be overriden by passing parameters

    BOOTSTRAP_INSTALLER_URL=${1-https://raw.githubusercontent.com/Shougo/dein.vim/master/bin/installer.sh}
    INSTALLER_FILE=${2-/tmp/installer.sh}
    INSTALLATION_DIRECTORY=${3-$HOME/.vim/bundles}


# Download the bootstrap installer and run it.

    echo "[*] Downloading the latest installer for Dein, the best VIM plugin manager"
    curl ${BOOTSTRAP_INSTALLER_URL} > ${INSTALLER_FILE}
    if [[ $? -ne 0 ]]; then
        echo "[!] Something has gone horribly wrong."
        [[ ! -f /tmp/installer.sh ]] && echo "[!] Failed create the installer file."
        exit 1
    fi
    echo "[*] Download complete."


# Make the bootstrap installer executable and run it

    echo "[*] Preparing to run the bootstrap installer"
    chmod +x ${INSTALLER_FILE}
    ${INSTALLER_FILE} ${INSTALLATION_DIRECTORY}
    if [[ $? -ne 0 ]]; then
        echo "[!] Something has gone horribly worng."
    fi
    exit 0
