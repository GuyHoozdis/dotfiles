# It looks like there are several interesting methods in this repo.
#
# DonneMartin's dev-tools repo
#
#   https://github.com/donnemartin/dev-setup/blob/master/.functions
#
# * fs - determine the total size of a file or directory
# * dataurl - Create a dataurl from a file
# * gitio - Create a git.io short URL
# * getcertnames - Show all the names (CNs and SANs) listed in the SSL
#       certification chain for a given host.
#
# Paul Irish's dotfiles repo
#
#   https://github.com/paulirish/dotfiles/blob/master/.functions
#
# * gifify - Create animated gifs from any video
# * webmify - Turn video into webm


# The `codetree` funciton is a wrapper for a specialized imvocation of `tree`.  The output
#  is color enabled, it excludes the .git and node_modules directories, pipes the output
#  into a pager where the color is preserved and line numbers are added.

    function codetree() {
        tree -aC -I '.git|node_modules|bower_components' --dirsfirst "$@" | less -FRNX;
    }


# The `dig-it` function is a wrapper around `dig` with some command line switches to
# give clean, yet verbose, output.

    function dig-it() {
        dig +nocmd "$1" any +multiline +noall +answer
    }


# Set the title, displayed on the tab, of the current terminal session.  I have to
# experiment with this to see if it gets overwritten when I run processes.

    function set-terminal-title {
        echo -ne "\033]0;"$*"\007"
    }


# Run iPython as a shell
#
# TODO: The shell profile, or perhaps its automated creation, should be checked
# in too.  I tend to base (i.e. load_subconfig()) off of develop, but there is
# more in that config than in my typical configurations... the things that make
# it an awesome shell... that stuff should definately be checked-in.

    function ipysh() {
      [[ ! -z ${IPYSH_DEBUG} ]] && set -x

      # Prefer the ipython from the current venv
      ipython=$(pyenv which ipython 2> /dev/null)
      if [[ $? -ne 0 ]]; then

        # If nothing is found, we'll still let the system try
        # to resolve the command.  If we find an explicit installation,
        # then we can overwrite the assumption.
        ipython=ipython
        pyenv_root=$(pyenv root)
        for venv in $(pyenv global); do
          fullpath=$pyenv_root/versions/$venv/bin/ipython
          [[ -f $fullpath ]] && ipython=$fullpath && break
        done
      fi

      [[ ! -z ${IPYSH_DEBUG} ]] && set +x
      ${ipython} --profile=shell $@
    }
