#!/usr/bin/env bash
#
#
set -eou pipefail


DOCKER_HUB_REGISTRY=registry.hub.docker.com/v2/repositories


function usage() {
  local appname=$(basename $0)
  echo "Usage: $appname  <owner> <container>"
  echo ""
  echo "Containers are generally identified by <owner>/<container>, with the exception"
  echo "of \"official\" containers.  In this case, pass the value \"official\" as the"
  echo "owner parameter (or \"_\" for shorthand)."
  echo ""
  echo "  owner     - The name of the owner of the repository."
  echo "  container - The name of the container."
  echo ""
  echo "Examples:"
  echo ""
  echo "  $ $appname library centos"
  echo ""
  echo "  $ $appname couchbase server"
  echo ""
  echo "  $ $appname couchbase sync-gateway"
}

[[ ! -z ${DEBUG:-} ]] && echo "Enable debug mode" && set -x
[[ $# < 2 ]] && echo "Mising required parameters" && usage && exit 2

owner=$1
container=$2
[[ "official" = "$owner" ]] && owner=_


http https://$DOCKER_HUB_REGISTRY/$owner/$container/tags/ | jq -r '.results[].name' | sort
