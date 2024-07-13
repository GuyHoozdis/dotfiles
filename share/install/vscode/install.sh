#!/usr/bin/env bash
## Install dotfiles inside VSCode Devcontainer
#
# This does not install everything - only the things that aren't already in the image and that I can't
# live without - like inputrc.
#
# Docs: https://code.visualstudio.com/docs/devcontainers/containers#_personalizing-with-dotfile-repositories
# Reference GuyHoozdis/devcontainer-experiment

echo "[*] Installing dotfiles for VSCode Dev Container."
echo "[-] CWD: ${PWD}"
cp etc/git/ignore ~/.gitignore
cp etc/inputrc ~/.inputrc
cp etc/bashrc.d/aliases.bash ~/.bash_aliases
cp etc/pdbrc ~/.pdbrc

# TODO: Configuring these is a little more complicated.  For now, if you need them manually configure.
#  - ipython profiles
#  - vim plugins
