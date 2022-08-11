#!/usr/bin/env bash
set -o pipefail

PROG=$(basename $0)
USAGE="Usage: $PROG [help|check|update]"

show_help() {
  cat <<HELP

  A utility to help identify when changes have occurred in
  the rlwrap source files.

  Commands: -----------------------------------------------------
   help     Shows this documentation.
   check    Compares the installed files in the filter directory
            against a set of known hashes.
   update   Update an existing set of known hashes or create a
            new set.
   -------  -----------------------------------------------------

  Since the filename is based on the rlwrap version; after an
  upgrade this utility might not be able to locate the stored
  known hashes.  Pass "RLWRAP_VERSION" on the command line with
  the appropriate version number (so that a set of hashes are
  found) and if no changes are reported, then you know that
  nothing changed in the update.

    $ RLWRAP_VERSION=$rlwrap_version $PROG check

  If the rlwrap version changes and the filter don't (i.e. the
  set of known hashes matches for two or more versions), then
  consider simply linking to the older shasums file instead of
  generating a new one.
HELP
}

# ==== Bootstrap =======================
if ! which -s rlwrap; then
  echo "rlwrap is not installed or not on the search path."
  exit 1
fi
rlwrap_version=${RLWRAP_VERSION-$(rlwrap -v)}

here=$(dirname $(realpath $0))
shasumsdir="${here}/shasums"
[ ! -d $shasumsdir ] && echo "Failed to locate $shasumsdir" && exit 1

shafile=${shasumsdir}/${rlwrap_version/ /-filters-}.sha256
if [ ! -f $shafile ]; then
  echo "Failed to locate known hashes: $shafile"
  exit 1
fi

# ==== Main Entry Point ================
[ 1 -ne $# ] && echo $USAGE && exit 1

command=$1
case "$command" in
  "help")
    echo $USAGE
    show_help
    exit 0
  ;;

  "check")
    echo
    echo -e "\e[32mChecking known hashes:\e[0m $shafile"
    echo
    shasum -a 256 -c $shafile | column -t
    RC=$?
    if [ 0 -ne $RC ]; then
      echo
      echo -e "\e[31mFiles have changed in the installed rlwrap filter direcoty!\e[0m"
    fi
    exit $?
  ;;

  "update")
    # It will be something like this, but there should be some care take to not overwrite
    # an existing shasum file.  Don't offer a force either... make the user move it, archive
    # it, or remove it themselves.
    #
    [ -f $shafile ] && echo "File exists!  Please archive $shafile" && exit 1
    echo "Command: $command"
    echo "Not implemented yet"
    #shasum -a 256 -p /usr/local/share/rlwrap/filters/* | tee $shafile
    exit 2
  ;;

  *)
    echo $USAGE
    echo "Unknown command: $command"
    exit 1
  ;;
esac
