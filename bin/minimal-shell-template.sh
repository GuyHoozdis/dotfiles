#!/usr/bin/env bash
#
# A template to use as a starting point for shell scripts.  To use or maintain
# this program:
#  1. Define the external utilities that are dependencies of this program in REQUIRED_PROGRAMS
#  2. Add program logic to "main" near the end of this template.
#
# ------------------------------------------------------------------------------
# Based on the "Minimal Safe Bash Script Template" article and the
# article 12-Factor CLI Apps.
#   https://betterdev.blog/minimal-safe-bash-script-template/
#   https://medium.com/@jdxcode/12-factor-cli-apps-dd3c227a0e46
#
# This is in contrast to the template I have that tries to adhere more closely
# to the Google Shell Style Guide.
# ==============================================================================


# ==============================================================================
# Script Environment Setup
# ==============================================================================
# Safer scripts with ...
#   https://vaneyckt.io/posts/safer_bash_scripts_with_set_euxo_pipefail/
# ... and when you may need to do something different.
#   https://www.reddit.com/r/commandline/comments/g1vsxk/the_first_two_statements_of_your_bash_script/fniifmk?utm_source=share&utm_medium=web2x&context=3
set -Eeuo pipefail
trap _cleanup SIGINT SIGTERM ERR EXIT


# ==============================================================================
# Global Variables
# ==============================================================================
# See the conversation
#   https://stackoverflow.com/a/4774063/4098450
# but use BASH_SOURCE[0].
SCRIPTNAME="$(basename "${BASH_SOURCE[0]}")"
SCRIPTPATH="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd -P)"
VERSION="0.1.0"
readonly SCRIPTNAME SCRIPTPATH VERSION

# Always check return values and give informative return values.
#   https://google.github.io/styleguide/shellguide.html#s8.1-checking-return-values
EXIT_SUCCESS=0
# generic error
EXIT_ERROR=1
# command line usage error
EXIT_USAGE=64
# data format error
EXIT_DATAERR=65
# cannot open input
EXIT_NOINPUT=66
# addressee unknown
EXIT_NOUSER=67
# host name unknown
EXIT_NOHOST=68
# service unavailable
EXIT_UNAVAILABLE=69
# internal software error
EXIT_SOFTWARE=70
# system error (e.g., can't fork)
EXIT_OSERR=71
# critical OS file missing
EXIT_OSFILE=72
# can't create (user) output file
EXIT_CANTCREAT=73
# input/output error
EXIT_IOERR=74
# temp failure; user is invited to retry
EXIT_TEMPFAIL=75
# remote error in protocol
EXIT_PROTOCOL=76
# permission denied
EXIT_NOPERM=77
# configuration error
EXIT_CONFIG=78
declare -rx EXIT_SUCCESS EXIT_ERROR EXIT_USAGE EXIT_DATAERR EXIT_NOINPUT EXIT_NOUSER EXIT_NOHOST EXIT_UNAVAILABLE
declare -rx EXIT_SOFTWARE EXIT_OSERR EXIT_OSFILE EXIT_CANTCREAT EXIT_IOERR EXIT_TEMPFAIL EXIT_PROTOCOL EXIT_NOPERM
declare -rx EXIT_CONFIG


# ==============================================================================
# Functions
# ==============================================================================

################################################################################
# Initialize the terminal escape codes for colored output.
# ------------------------------------------------------------------------------
# Globals:
#   TERM
#   NO_COLOR
# Arguments:
#   None
################################################################################
function _setup_colors() {
  if [[ -t 2 ]] && [[ -z "${NO_COLOR-}" ]] && [[ "${TERM-}" != "dumb" ]]; then
    RESET='\033[0m' RED='\033[0;31m' GREEN='\033[0;32m' ORANGE='\033[0;33m' \
    BLUE='\033[0;34m' PURPLE='\033[0;35m' CYAN='\033[0;36m' YELLOW='\033[1;33m'
  else
    RESET='' RED='' GREEN='' ORANGE='' BLUE='' PURPLE='' CYAN='' YELLOW=''
  fi
  declare -rx RESET RED GREEN ORANGE BLUE PURPLE CYAN YELLOW
}


################################################################################
# Direct the message to stderr without further modification.
# ------------------------------------------------------------------------------
# Globals:
#   None
# Arguments:
#   msg     Defaults to empty string
################################################################################
function stderr() {
  local msg="${1-}"

  # TODO(guyhoozdis): Make this more like your format-message() function
  # that uses printf and string interpolation.
  echo >&2 -e "${msg}"
}

################################################################################
# Decorate and emit the message conveying information for the user.
# ------------------------------------------------------------------------------
# Globals:
#   None
# Arguments:
#   msg     Defaults to empty string
################################################################################
function log() {
  local msg="[${GREEN}-${RESET}] ${1-}"
  stderr "${msg}"
}

################################################################################
# Decorate and emit the message indicating a non-critical error has occurred.
# ------------------------------------------------------------------------------
# Globals:
#   None
# Arguments:
#   msg     Defaults to empty string
################################################################################
function warn() {
  stderr "[${YELLOW}*${RESET}] ${1-}"
}

################################################################################
# Decorate and emit the message indicating an critical error has occurred.
# ------------------------------------------------------------------------------
# Globals:
#   None
# Arguments:
#   msg     Defaults to empty string
################################################################################
function error() {
  stderr "[${RED}*${RESET}] ${1-}"
}

################################################################################
# Log error message and exit program.
# ------------------------------------------------------------------------------
# Globals:
#   EXIT_ERROR
# Arguments:
#   msg         Required parameter
#   exitcode    Defaults to 1 - EXIT_ERROR
################################################################################
function die() {
  local msg="$1"
  local exitcode="${2-$EXIT_ERROR}"

  error "${msg}"
  exit "${exitcode}"
}


################################################################################
# Display program usage help and exit pogram.
# ------------------------------------------------------------------------------
# Globals:
#   EXIT_SUCCESS
#   SCRIPTNAME
# Arguments:
#   exitcode    Defaults to 0 - success
################################################################################
function usage() {
  local exitcode=${1-$EXIT_SUCCESS}

  cat <<EOF
Usage: ${SCRIPTNAME} [options] arg1 arg2 [...argN]

Script description here.

Available options:

-h, --help      Print this help and exit
-v, --verbose   Print script debug info
-f, --flag      Some flag description
-p, --param     Some param description
--version       Print the script's version number.
EOF
  exit "${exitcode}"
}


################################################################################
# Custom clean up logic called upon program exit
# ------------------------------------------------------------------------------
# Globals:
#   None
# Arguments:
#   None
################################################################################
function _cleanup() {
  trap - SIGINT SIGTERM ERR EXIT
  #
  # Add cleanup logic here.
  #
}


################################################################################
# Verify required programs are installed on host or exit with error code.
# ------------------------------------------------------------------------------
# Globals:
#   EXIT_CONFIG
# Arguments:
#   None
################################################################################
function _check_required_programs() {
  # Required program(s)
  local -a req_progs=(git awk)
  for p in "${req_progs[@]}"; do
    # XXX: This approach, using `hash`, does not seem to work for everything.  Switch to using `which`.
    hash "${p}" 2>&- || \
	    { echo >&2 " Required program \"${p}\" not installed or in search PATH."; exit $EXIT_CONFIG; }
  done
}


################################################################################
# Parse commandline options and arguments.
# ------------------------------------------------------------------------------
# Globals:
#   SCRIPTNAME
#   VERSION
#   EXIT_SUCCESS
#   EXIT_USAGE
# Arguments:
#   *       Consumes $@
################################################################################
function _parse_params() {
  # default values of variables set from params
  flag=0
  param=''

  while :; do
    case "${1-}" in
    -h | --help) usage ;;
    -v | --verbose) set -x ;;
    --no-color) NO_COLOR=1 ;;
    -f | --flag) flag=1 ;; # example flag
    -p | --param) # example named parameter
      param="${2-}"
      shift
      ;;
    --version)
      stderr "${SCRIPTNAME} v${VERSION}"
      exit $EXIT_SUCCESS
      ;;
    -?*)
      error "Unknown option: $1"
      usage "$EXIT_USAGE"
      ;;
    *) break ;;
    esac
    shift
  done

  args=("$@")

  # check required params and arguments
  [[ -z "${param-}" ]] && die "Missing required parameter: param"
  [[ ${#args[@]} -eq 0 ]] && die "Missing script arguments"

  return $EXIT_SUCCESS
}


################################################################################
# Program entrypoint
# ------------------------------------------------------------------------------
# Globals:
#   SCRIPTPATH
#   SCRIPTNAME
# Arguments:
#   None
################################################################################
function main() {
  log "Executing ${SCRIPTPATH}/${SCRIPTNAME}"
  log "Read parameters:"
  log "- flag: ${flag}"
  log "- param: ${param}"
  log "- arguments: ${args[*]-}"
  # script logic here

}

# Initialize program
_setup_colors
_check_required_programs
_parse_params "$@"

# Invoke entrypoint
main
exit $?
