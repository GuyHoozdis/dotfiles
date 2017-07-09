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

    brew install git
    brew install the_silver_searcher
    brew install pyenv


# Look into these
#
#  * https://github.com/junegunn/fzf
#  * https://github.com/rupa/z
#  * https://www.ivarch.com/programs/pv.shtml

    #brew install z
    #brew install fzf
    #brew install pv
