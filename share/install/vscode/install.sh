#!/usr/bin/env bash
## Install dotfiles inside VSCode Devcontainer
#
# This does not install everything - only the things that aren't already in the image and that I can't
# live without - like inputrc and ipython configured with vi-keybindings.
#
# Docs: https://code.visualstudio.com/docs/devcontainers/containers#_personalizing-with-dotfile-repositories
# Reference: gh:GuyHoozdis/devcontainer-experiment


function _setup_colors() {
  if [[ -t 2 ]] && [[ -z "${NO_COLOR-}" ]] && [[ "${TERM-}" != "dumb" ]]; then
    RESET='\033[0m' RED='\033[0;31m' GREEN='\033[0;32m' ORANGE='\033[0;33m' \
    BLUE='\033[0;34m' PURPLE='\033[0;35m' CYAN='\033[0;36m' YELLOW='\033[1;33m'
  else
    RESET='' RED='' GREEN='' ORANGE='' BLUE='' PURPLE='' CYAN='' YELLOW=''
  fi
  declare -rx RESET RED GREEN ORANGE BLUE PURPLE CYAN YELLOW
}

function _is_installed() {
  local returncode=0
  local application=${1?"[!] Missing required argument."}
  if [ $# -gt 1 ]; then
    echo "[!] Too many arguments."
    exit 1
  fi

  if ! which "${application}" &>/dev/null; then
    echo "[-] ${application} is not installed."
    returncode=1
  fi

  return $returncode
}


_setup_colors
echo -e "[*] ${GREEN}Installing dotfiles for VSCode Dev Container${RESET}."
echo "[-] CWD: ${PWD}"
echo -e "[!] ${RED}VSCode executes this script from the root of the dotfiles directory${RESET}."
echo -e "[!] ${RED}That is the only scenario that is currently supported${RESET}."

echo -e "[*] ${GREEN}Installing standard user configuration files${RESET}."
# VSCode already copies and adds to .gitconfig, so don't overwrite it.
cp etc/git/ignore ~/.gitignore
cp etc/inputrc ~/.inputrc
cp etc/bashrc.d/aliases.bash ~/.bash_aliases
cp etc/pdbrc ~/.pdbrc

if ! _is_installed ipython; then
  echo -e "[*] ${GREEN}Installing ipython${RESET}."
  if _is_installed pipx; then
    pipx install ipython
  else
    pip install ipython
  fi
fi

echo -e "[*] ${GREEN}Creating ipython default profile${RESET}."
if [ -d "${HOME}/.ipython/profile_default" ]; then
  echo "[-] Default profile already exists."
else
  ipython profile create
fi

echo -e "[*] ${GREEN}Installing custom default profile${RESET}."
cp -f etc/ipython/profile_default/ipython_config.py ~/.ipython/profile_default/
