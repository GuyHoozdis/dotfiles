#!/usr/bin/env bash
###############################################################################
## Determine if a specified port on a given host is open.
#
# When you find yourself on a *nix system that doesn't have the typical
# utilities that would be used to do this same task (and more... better) are
# not available - that's when I use this tool.  Netcat (usually installed as
# a part of the system) or Nmap are better choices, but may not be available
# on a locked-down system or system that you don't control.
###############################################################################

set -eou pipefail

PORT_OPEN=0
HOSTNAME_RESOLVES=0
NO_RESPONSE=1
UNKNOWN_ERROR=-1


function usage() {
  local appname=$(basename $0)
  echo "Usage: $appname <hostname> <port> [message]"
  echo ""
  echo " Determine if a given port is open on the indicated host."
  echo ""
  echo " Arguments:"
  echo "  hostname  - Hostname or IP address of the interface to probe."
  echo "  port      - Port number to probe."
  echo "  message   - Optional message/content to send to specified port"
  echo ""
  echo " Examples:"
  echo "  $ $appname google.com 80 && echo $?"
  echo "  (open) Port 80 on google.com appears to be open."
  echo "  0"
  echo ""
  echo "  $ $appname notgoogle.com 80 || echo $?"
  echo "  (closed) Port 80 on notgoogle.com does not appear to be open."
  echo "  (no route) oh no!"
  echo "  1"
  echo ""
  echo "  $ $appname google.com $(( 16#50 )) && echo $?"
  echo "  (open) Port 80 on google.com appears to be open."
  echo "  0"
}


function probe-port() {
  local hostname=${1?Missing required parameter "hostname"}
  local port=${2?Missing required parameter "port"}
  local message=${3-""}
  local return_code=$UNKNOWN_ERROR

  if (echo "$message" > /dev/tcp/$hostname/$port) &> /dev/null ; then
    echo "(open) Port $port on $hostname appears to be open."
    return_code=$PORT_OPEN
  else
    echo "(closed) Port $port on $hostname does not appear to be open."
    return_code=$NO_RESPONSE
  fi

  return $return_code
}


function resolve-hostname() {
  local hostname=${1?Missing required parameter "hostname"}
  local return_code=$UNKNOWN_ERROR

  answer=$(dig +short $hostname)
  if [[ ${#answer} -gt 0 ]]; then
    echo "(resolved) The host $hostname appears to be up."
    return_code=$HOSTNAME_RESOLVES
  else
    echo "(no route) oh no!"
    return_code=$NO_RESPONSE
  fi

  return $return_code
}


## Main Entry point
[[ ! -z ${DEBUG:-} ]] && echo "Enabling debug mode" && set -x
[[ $# -lt 2 ]] && echo "Missing required parameters" && usage && exit 1

HOSTNAME=$1
PORT=$2
MESSAGE=${3-""}

probe-port $HOSTNAME $PORT $MESSAGE || resolve-hostname $HOSTNAME
exit $?
