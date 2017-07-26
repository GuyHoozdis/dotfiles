#!/usr/bin/env bash

# #######################################
# Install common applications
#
#  Inspired by Paul Irish's brew-cask.sh
# #######################################


# Manulaly maintain the casks
#
#   brew update && brew upgrade brew-cask && brew cleanup && brew cask cleanup



    brew install caskroom/cask/brew-cask


# Go checkout Paul's `brew-cask.sh`. There were several things
# that I thought were interesting, but they are not a part of 
# my daily workflow.


    brew cask install iterm2
    brew install wireshark --with-gtk+
    brew cask install virtualbox
    brew cask install skitch
