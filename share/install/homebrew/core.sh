#!/usr/bin/env bash

# ####################################
# Install the core command-line tools.
#
#  Inspired by Paul Irish's brew.sh
# ####################################

    brew update
    brew upgrade


# GNU core utilities
#
#  * coreutils - https://www.gnu.org/software/coreutils/coreutils.html
#  * findutils - https://www.gnu.org/software/findutils/
#  * https://www.gnu.org/software/gawk/

    brew install coreutils
    brew install findutils
    brew install gawk
    brew install tree
    brew install readline

# !!!: This was really tedious to get working, but it did work.  I only needed it
# to get vi-bindings in a node REPL.  I haven't used that in a while, so hold off
# on this and go back over the whole install and setup process again.  Maybe it has
# changed and is easier now.
    #brew install rlwrap


# Bash 5
# Note: Don't forget to add `/usr/local/bin/bash` to `/etc/shells` before running `chsh`.
#
#  * https://www.gnu.org/software/bash/
#  * https://github.com/scop/bash-completion

    brew install bash
    brew install bash-completion


# Development tools
#
#  * https://git-scm.com/
#  * https://github.com/ggreer/the_silver_searcher
#  * https://hub.github.com/
#  * https://github.com/joeyespo/grip
#  * https://github.com/DanielVartanov/willgit
#  * ...

    brew install git
    brew install git-flow
    brew install hub
    brew install the_silver_searcher
    brew install jq
    brew install httpie
    brew install mitmproxy
    brew install editorconfig

# !!!: Review these tools to see if you want to keep them.
    #brew install willgit
    #brew install grip
    #brew install awscli
    #brew install z

    # Install nmap with the GUI commponent
    brew install nmap --with-pygtk


# Platform version managers
#
#  * https://github.com/pyenv/pyenv
#  * https://github.com/tj/n
#  * https://github.com/rbenv/rbenv

    brew install pyenv
    brew install pyenv-virtualenv
    brew install rbenv


# !!!: Disabling this while I check to see if it still needs my work around.
# Node version manager
#
# The brew script seems to be evolving (for the better), but it still needs
# a little help preparing directories.

    #brew install n
    #sudo mkdir -p /usr/local/n/versions/{node,ios}
    #eval $(stat -s $(brew --cellar))
    #sudo chown -R $st_uid:$st_gid /usr/local/n


# XXX: Disabling these because I use docker instead of a local install.
# Databases
#
#  * MySQL (I eff-ing hate you MySQL)
#  * PostgreSQL
#  * Redis
#  * Mongo

    #brew install percona-server
    #brew install redis
    #brew install libcouchbase

    #brew install postgresql
    #brew install mongo


# Look into these
#
#  * https://github.com/junegunn/fzf
#  * https://github.com/rupa/z
#  * https://www.ivarch.com/programs/pv.shtml

    #brew install fzf
    #brew install pv


# These are all things that I want to look into too
#
# - imagemagick
# - ffmpeg
# - pidcat
# - android-platform-tools
# - ncdu
# - terminal-notifier
# - homebrew/completions/brew-cask-completion
# - zmap (https://zmap.io - saw during a runZero webinar)
