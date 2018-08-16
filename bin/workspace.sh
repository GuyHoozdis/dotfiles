#!/usr/bin/env bash

set -eou pipefail


# TODO: If you start using this tool, then spend some time fleshing it out.

WORKSPACE_ROOT=.tmp
WORKSPACE_NAME=${1?Missing parameter for workspace name}


printf "[*] Creating workspace: %s\n" "$WORKSPACE_NAME"
mkdir -p "$WORKSPACE_ROOT/$WORKSPACE_NAME"

if [[ -h ./tmp ]]; then
  printf "[*] Unlinking existing workspace\n"
  rm -i tmp
fi

printf "[*] Linking ./tmp/ to %s\n" "$WORKSPACE_NAME"
ln -s "$WORKSPACE_ROOT/$WORKSPACE_NAME" tmp
