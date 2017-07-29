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


# Bash 4    
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
#  * ...

    brew install git
    brew install git-flow
    brew install hub
    brew install the_silver_searcher
    brew install jq
    brew install httpie
    brew install mitmproxy
    brew install awscli
    #brew install z

    # !!!: I'll have to look closer at how these get applied in a virgin system.
    #  * Will `docker-compose` install `docker-machine` since it is a dependancy?
    #  * Do these need to occur after `VirtualBox` is installed?  (See cask.sh)
    brew install docker-machine
    brew install docker-compose

    #
    brew install nmap


# Platform version managers
#
#  * https://github.com/pyenv/pyenv
#  * https://github.com/tj/n
#  * https://github.com/rbenv/rbenv

    brew install pyenv
    brew install pyenv-virtualenv
    brew install n
    #brew install rbenv

# !!!: It appears that when _n_ is installed via brew there is an issue that
# doesn't exist, I don't recall it anyway, when installing via npm.  The problem
# is that _n_ does not create the directory, where it keeps downloaded versions of
# node, during installation.  It tries to create the directory, at /usr/local/n by
# default, the first time it runs.
#
# I believe, when brew is doing the install that it has elevated privileges and it
# could have created the directory `/usr/local/n`.  The owner of `/usr/local` is
# `root:wheel`; hence, when the utility runs for the first time, my user, it doesn't
# have the permissions to create `/usr/local/n/{node,ios}`.
#
# Setting N_PREFIX might be analternative, but it seems that it will expect a
# bin directory to be at `$N_PREFIX/bin`.  That doesn't follow any the FHS :/.
#
# I think this will pre-create the directories for _n_, so that it by the time it
# runs fo the first time it is happy.

    sudo mkdir -p /usr/local/n/{node,ios}
    eval $(stat $HOME)
    sudo chown -R $st_uid:$st_gid /usr/local/n


# Databases
#
#  * MySQL (I eff-ing hate you MySQL)
#  * PostgreSQL
#  * Redis
#  * Mongo

    brew install percona-server
    brew install postgresql
    brew install redis
    brew install mongo


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
