# The exports are sourced before this, so those values are available
# to be used in this module.  In pseudo code; the load order goes
# like this:
#
#   for filename in {exports,aliases,functions,app-config,prompt};
#     load filename.local.bash if filename.local.bash exists;
#     load filename.bash if filename.bash exists;
#
# -----------------------------------------------------------------------------

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
#  is color enabled, it excludes the .git and everyting defined in .gitignore, pipes the output
#  into a pager where the color is preserved and line numbers are added.

    function codetree() {
        local ignore='.git|.ruff_cache'
        tree -aC -I $ignore --gitignore --dirsfirst "$@" | less -FRNX;
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


# Check for key/element in an array
#
# !!!: Keys must be quoted in the array or this technique will not match them :(  Consider
#      a grep variation over the keys
#   local keys=${!container[@]}
#   printf "%s\n" $keys | grep -q ^$key

    function exists() {
      if [ "$2" != "in" ] || [ $# -ne 3 ]; then
        printf "Usage: ${FUNCNAME[0]} [key] in [array]"
        return
      fi

      local key=$1
      local container=$3
      eval '[ ${'$container'[$key]+TheItemYouSeekExistsInTheIndicatedContainer} ]'

      # !!!: If the above technique doesn't work, consider this.
      #eval 'local keys=${!'$1'[@]}';
      #eval "case '$2' in
      #  ${keys// /|}) return 0 ;;
      #  * ) return 1 ;;
      #esac";
      #}
    }

#    function initialize-pyenv() {
#      if [[ ! -z $VIRTUAL_ENV ]]; then
#        echo "Detected VIRTUAL_ENV as non-zero: $VITUAL_ENV"
#        return 1
#      fi
#
#      # This will reload colors for prompt labels
#      #export PYENV_ACTIVE=initializing
#      export PYENV_VIRTUALENV_DISABLE_PROMPT=1
#      if which -s pyenv; then
#           eval "$(pyenv init -)"
#      else
#          echo "Failed to initialize PyEnv"
#          return 1
#      fi
#      if which -s pyenv-virtualenv; then
#          eval "$(pyenv virtualenv-init -)"
#      else
#          echo "Failed to initialize PyEnv VitualEnv"
#          return 1
#      fi
#
#      export PYENV_ACTIVE=active
#    }

# Color/Style Shell Messages
#
# TODO: Background color accent is not yet implmented

    function format-message() {
      declare -A styles
      declare -A colors
      local styles=(["normal"]=0 ["bold"]=1 ["dim"]=2 ["italic"]=3 ["underline"]=4)
      local colors=(["black"]=30 ["red"]=31 ["green"]=32 ["yellow"]=33 ["blue"]=34 ["purple"]=35 ["cyan"]=36 ["white"]=37)

      # TODO: Re-write the help text as a HEREDOC and redirect output to stderr.
      #  cat - >&2 <<EOM
      #  Usage: [STYLE=normal] [COLOR=white] [ORS=\\n] ${FUNCNAME[0]} <FMT> [ARG...]
      #
      #    STYLE - ...
      #    COLOR - ...
      #
      #.... snip ....
      #
      #  EOM
      if [ $# -eq 0 ]; then
        printf 'Usage: [STYLE=normal] [COLOR=white] [ORS=\\n] %s <FMT> [ARG...]\n' ${FUNCNAME[0]}
        printf '\n'
        printf '  STYLE - Styling to apply (normal, bold, dim, underline, italic)\n'
        printf '  COLOR - Colors (black, red, green, yellow, blue, purple, cyan, white)\n'
        printf '    ORS - Output record seperator.\n'
        printf '\n'
        printf 'Examples:\n'
        printf '\n'
        printf '  Color a simple message w/o any variable replacement.\n'
        printf '  $ COLOR=red %s "color me bad"\n' ${FUNCNAME[0]}
        printf '\n'
        printf '  Format a message template from arguments.\n'
        printf '  $ COLOR=red %s "color %%s %%s" me bad\n' ${FUNCNAME[0]}
        printf '\n'
        printf '  Apply both color and style.\n'
        printf '  $ COLOR=green STYLE=bold %s "color %%s %%s" you good\n' ${FUNCNAME[0]}
        printf '\n'
        printf '  Enclose complex parameters in quotes.\n'
        printf '  $ COLOR=blue STYLE=underline %s "color %%s %%s" me "both good and bad simultaneously"\n' ${FUNCNAME[0]}
        printf '\n'
        printf '  Render multiple messages (seperated by a newline by default).\n'
        printf '  $ COLOR=blue %s "%%s" a b c d\n' ${FUNCNAME[0]}
        printf '  $ COLOR=blue %s "%%s" "a b" c d\n' ${FUNCNAME[0]}
        printf '\n'
        printf '  Change the ORS to create comma-seperated output (Notice color/style is not applied to the ORS).\n'
        printf '  $ COLOR=cyan ORS=", " %s "%%s" a b c d\n' ${FUNCNAME[0]}
        printf '  $ COLOR=cyan ORS=", " %s "%%s" "a b" c d\n' ${FUNCNAME[0]}
        printf '\n'
        printf '  Replace printf (Intended to emphasize the similarity in behavior, not a recommendation).\n'
        printf '  $ alias printf=format-message\n'
        printf '  $ COLOR=cyan printf "%%s" one two three\n'
        printf '  $ \printf "%%s" "Execute the original command" "instead of the alias" "by preceding the command with a backslash"\n'
        return 1
      fi

      # Assume the first parameter is a string template.  Doing this ensures that the behavior of this function, with regard
      # to processing arguments while rendering a string template, is identical to printf.
      local FMT=$1; shift;

      # By default, this function post-pends a newline character to the string format template - printf does not do that.
      printf "\e[${styles[${STYLE:-normal}]};${colors[${COLOR:-white}]}m${FMT}\e[0m${ORS:-\n}" "$@"
    }


# JSON CLI Utilities

if ! which -s jq; then
  function jqless() {
    echo "You need to install 'jq' first, then start a new terminal session"
  }
else
  function jqless() {
    [[ -z $# ]] && echo "Missing required input!"

    # Intentionally not using `set -o pipefail`
    jq -C $@ | less -R --quit-if-one-screen
    return ${PIPESTATUS[0]}
  }
fi


# NOTE: Trying this out to see if it obviates the need for me to put more work into my devenv utility.
if ! which -s pyenv; then
  function pyenv-venv-reset() {
    echo "You need to install (or initialize) pyenv"
  }
else
  function pyenv-venv-reset() {
    if [ $# -eq 0 ]; then
      cat - >&2 <<EOM

Usage: ${FUNCNAME[0]} <VENV_DIR>

  Delete an existing virtualenv and recreate it.  Preserve the '.python-version' file, if
  it exists.

  Args:
    VENV_DIR - the full or relative path to the virtual environment directory.

  Env Vars:
    PYTHON - the python command to use to create the virtual environment.  Defaults to 'python3'.
EOM
      return 0
    fi

    local name="${1:-.venv}"
    if [ ! -d ${name} ]; then
      COLOR=red format-message "Invalid input - ${name} is not a path to a virtual env." >&2
      return 1
    elif [ ! -f ${name}/pyvenv.cfg ]; then
      COLOR=red format-message "Invalid input - ${name} is not a virtual env." >&2
      return 1
    fi

    if [ -f .python-version ]; then
      mv .python-version break-python-version
    fi
    local python_cmd=${PYTHON:-python3}

    rm -rf ${name}
    ${python_cmd} -m venv ${name}
    if [ -f break-python-version ]; then
      mv break-python-version .python-version
    fi
  }
fi

# ===========================================================================
# Create a Python virtual environment using python3 -m venv.
#
# TODO: This was a quick-and-dirty creation, but it could be much
# better.  If it turns out to be useful, then spend some more time on it.
#
# XXX: This assumes that $1 is either `-h/--help` or the name of a virtual
# environment.  It would be better if it simply passed $@ to the
# `python3 -m venv` command, but then the checks and error messages would
# all be impossible.
#
# XXX: As it stands, there are two code paths that try to display help
# info and they both output something different. :(
function mkvenv() {
  local RED='\033[0;31m' GREEN='\033[0;32m' NC='\033[0m'
  local venv_name=$1
  local python_cmd=${PYTHON:-python3}
  shift;

  # Check to see if parameter is -h or --help
  # if so, pass -h to python3 -m venv.
  if [[ "$venv_name" == "-h" || "$venv_name" == "--help" ]]; then
    $python_cmd -m venv $venv_name
    return 0
  fi
  if [ -z "$venv_name" ]; then
    echo -e "Usage: ${GREEN}mkvenv <venv_name> [<options>]${NC}"
    return 1
  fi

  if [ -d "$venv_name" ]; then
    echo -e "${RED}Virtual environment ${NC}$venv_name ${RED}already exists.${NC}"
    return 1
  fi

  if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${GREEN}Creating virtual environment...${NC}"
    if $python_cmd -m venv "$venv_name" "$@"; then
      source "$venv_name/bin/activate"
      echo -e "${GREEN}Virtual environment ${NC}$venv_name ${GREEN}created and activated.${NC}"
      pip install --upgrade pip setuptools
      echo -e "${GREEN}Updated pip and setuptools.${NC}"
    fi
  else
    echo -e "${RED}You are already in a virtual environment. Please deactivate it first.${NC}"
    return 1
  fi

  return 0
}
