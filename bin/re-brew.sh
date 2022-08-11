#!/usr/bin/env bash
# ==============================================================================
# === Install previous versions of an application via Homebrew
#
# The basic idea/technique for this utility comes from:
#
#   https://www.client9.com/using-macos-homebrew-to-install-a-specific-version/
#
# Looking up the hash that corresponds to the desired version of the formula
# desired is still a manual process.
#
# Example values:
#
# NAME=docker
# HASH=b55e8d0694c8a9916eba477f16f248b1a966872c
#
# Also, some documentation on a, possibly programatic way to find the hash
# of older versions of the package you are looking for.
#
#   https://docs.brew.sh/Querying-Brew
#
# $ brew info --json=v1 --all <formula> > some-very-large-file.json && badge
# $ jq -C '.[] | select(.name == <formula>)' some-very-large-file.json | less -R
#
# ^^^ That appears to only search the local info though.  :/ .  Would need to
# fetch an unshallow history.
#
# $ git -C "$(brew --repo homebrew/core)" log master -- Formula/phantomjs.rb
#
#
# This appears to works too..
#
# $ http https://github.com/Homebrew/homebrew-core/commits/master/Formula/docker.rb
#
# ...but would need to be parsed.

set -eou pipefail


BREW_URL=https://raw.githubusercontent.com/Homebrew/homebrew-core
APP=$(basename $0)


function usage() {
  echo "Usage: $APP <COMMAND> [ARG...]"
  echo ""
  echo " Commands:"
  echo "  versions"
  echo "  install"
  echo "  "
  echo "  versions"

}


COMMAND=$1
# NAME=$1
# HASH=b55e8d0694c8a9916eba477f16f248b1a966872c
# brew unlink docker
# brew install ${BREW_URL}/${HASH}/Formula/${NAME}.rb
