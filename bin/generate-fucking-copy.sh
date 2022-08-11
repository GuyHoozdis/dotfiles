#!/usr/bin/env bash
set -eou pipefail


RED="\033[31m"
GREEN="\033[32m"
YELLOW="\033[33m"
END="\033[00m"


[[ ${DEBUG-""} ]] && printf "${GREEN}Debugging enabled${END}" && set -x


function is_utility_on_bin_path() {
  local required_error_message="You must install '%s' for HTML parsing of the response."
  local success=0
  local utility=$1

  if ! which -s $utility; then
    printf "$required_error_message" $utility
    success=1
  fi
  return $success
}


function required_utilities_installed() {
  if is_utility_on_bin_path "pup" && is_utility_on_bin_path "http"; then
    return 0 
  fi
  return 1
}


function usage() {
  local app=$(basename $0)
  echo "Usage: $app <type> <n>"
  echo ""
  echo "  Arguments:"
  echo "    type  - The type of content to generate; one of (words, paragraphs)"
  echo "    n     - The number of the selected type to generate; a positive integer"
  echo ""
  echo "  Examples:"
  echo "    Generate some output."
  echo "      $ $app words 5"
  echo ""
  echo "    Format paragraph output and copy to clipboard"
  echo "      $ $app paragraphs 2 | fold -w 100 -s | pbcopy"
}



if ! required_utilities_installed; then
  printf "${YELLOW}%s${END}" "Missing utilities can be installed via Homebrew on OSX systems"
  exit 1
fi
[[ $# -eq 1 ]] && [[ "help" = "${1-help}" ]] && usage && exit 0
[[ $# -lt 2 ]] && printf "${RED}%s${END}" "Missing required parameters" && exit 1

REQCOPY=${1,,} ; [[ words = $REQCOPY || paragraphs = $REQCOPY ]] || (printf "${RED}'%s' is not a valid type of copy" $REQCOPY ; usage ; exit 1)
NUMCOPY=$2 ; [[ $NUMCOPY =~ ^-?[0-9]+$ ]] || (printf "${RED}'%s' is not a digit${END}" $2 ; usage ; exit 1)


#unset RED GREE YELLOW END
printf "${GREEN}Generating %s %s of fucking copy${END}\n\n" $NUMCOPY $REQCOPY
http loremfuckingipsum.com/text.php number-copy=$NUMCOPY copy=Paragraphs --form --body --stream \
  | tee /tmp/lfipsum-response.html \
  | pup 'div#text-to-copy text{}' \
  | tee /tmp/lfipsum-parsed.txt
