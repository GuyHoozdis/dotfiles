# Login shells load exports; interactive shells load shell-options, aliases,
# functions, app-config, and prompt, in that order. Each module's .local.bash
# override is sourced before its tracked .bash file.
#
# -----------------------------------------------------------------------------

# Export Homebrew Environment
# - On Apple Silicon Homebrew installs under `/opt/homebrew` instead of `/usr/local` (it does this to
#   avoid requiring `sudo` and/or requiring `chmod -R <foo>:<bar> /usr/local`).
# - If `brew` isn't configured when things like `pyenv` or `gls` are used or even tested if they are
#   installed, then things won't work as expected.
# - That is why this has to be done pretty early on.

  function initialize_homebrew() {
    local path_suffix=bin/brew
    if [ -x /usr/local/${path_suffix} ]; then
      homebrew_prefix=/usr/local
      eval "$(/usr/local/${path_suffix} shellenv)"
    elif [ -x /opt/homebrew/$path_suffix ]; then
      homebrew_prefix=/opt/homebrew
      eval "$(/opt/homebrew/${path_suffix} shellenv)"
    fi
  }

  function exists_in_path () {
    target=$1
    echo -e ${PATH//:/\\n} | egrep "^${target}$" &>/dev/null
    return $?
  }

  # The output array is local to the reconstruction function via dynamic scope.
  function _dotfiles_split_path() {
    local rest=$1
    _dotfiles_path_parts=()
    while [[ $rest == *:* ]]; do
      _dotfiles_path_parts[${#_dotfiles_path_parts[@]}]="${rest%%:*}"
      rest=${rest#*:}
    done
    _dotfiles_path_parts[${#_dotfiles_path_parts[@]}]="$rest"
  }

  function _dotfiles_path_contains() {
    local target=$1 entry
    shift
    for entry in "$@"; do
      [[ $entry == "$target" ]] && return 0
    done
    return 1
  }

  function _dotfiles_rebuild_path() {
    local incoming_path=$1 provider_path=$2 brew_prefix=$3 baseline=$4 baseline_home=$5
    local entry managed_entry previous_rank rank i anchor valid found result separator
    local -a _dotfiles_path_parts incoming provider prior home_managed managed
    local -a shared_prior shared_incoming baseline_tail callers output consumed

    home_managed=("$HOME/.local/bin" "$HOME/node_modules/.bin" "$HOME/.n/bin"
      "$HOME/.rbenv/shims" "$HOME/.pyenv/shims" "$HOME/.go/bin"
      "$HOME/.bun/bin" "$HOME/.dotnet/tools")
    managed=("${home_managed[@]}")
    if [[ -n $brew_prefix ]]; then
      managed[${#managed[@]}]="$brew_prefix/bin"
      managed[${#managed[@]}]="$brew_prefix/sbin"
    fi
    _dotfiles_split_path "$incoming_path"
    incoming=("${_dotfiles_path_parts[@]}")
    _dotfiles_split_path "$provider_path"
    provider=("${_dotfiles_path_parts[@]}")
    _dotfiles_split_path "$baseline"
    prior=("${_dotfiles_path_parts[@]}")

    # A missing, stale or structurally invalid snapshot provides no provenance.
    valid=1
    [[ -n $baseline && $baseline_home == "$HOME" ]] || valid=0
    previous_rank=-1
    shared_prior=()
    for entry in "${prior[@]}"; do
      rank=0
      for managed_entry in "${home_managed[@]}"; do
        if [[ $entry == "$managed_entry" ]]; then
          (( rank > previous_rank )) || valid=0
          previous_rank=$rank
          if _dotfiles_path_contains "$entry" "${incoming[@]}"; then
            shared_prior[${#shared_prior[@]}]="$entry"
          fi
          break
        fi
        ((rank+=1))
      done
    done
    shared_incoming=()
    for entry in "${incoming[@]}"; do
      if _dotfiles_path_contains "$entry" "${shared_prior[@]}"; then
        shared_incoming[${#shared_incoming[@]}]="$entry"
      fi
    done
    [[ ${#shared_prior[@]} -gt 0 && ${#shared_prior[@]} -eq ${#shared_incoming[@]} ]] || valid=0
    for ((i=0; i<${#shared_prior[@]}; i++)); do
      [[ ${shared_prior[i]} == "${shared_incoming[i]-}" ]] || valid=0
    done

    callers=()
    if (( valid )); then
      anchor=${shared_prior[0]}
      baseline_tail=()
      found=0
      for entry in "${prior[@]}"; do
        [[ $entry == "$anchor" ]] && found=1
        (( found )) && baseline_tail[${#baseline_tail[@]}]="$entry"
      done
      for entry in "${incoming[@]}"; do
        [[ $entry == "$anchor" ]] && break
        if ! _dotfiles_path_contains "$entry" "${managed[@]}" &&
           ! _dotfiles_path_contains "$entry" "${baseline_tail[@]}"; then
          callers[${#callers[@]}]="$entry"
        fi
      done
    fi

    output=("${callers[@]}")
    for entry in "${home_managed[@]}"; do
      if [[ $entry == "$HOME/.go/bin" ]] ||
         { [[ $entry == "$HOME/.local/bin" || $entry == "$HOME/node_modules/.bin" || $entry == "$HOME/.bun/bin" ]] && [[ -d $entry ]]; } ||
         _dotfiles_path_contains "$entry" "${incoming[@]}" ||
         _dotfiles_path_contains "$entry" "${provider[@]}"; then
        output[${#output[@]}]="$entry"
      fi
    done
    if [[ -n $brew_prefix ]]; then
      for entry in "$brew_prefix/bin" "$brew_prefix/sbin"; do
        output[${#output[@]}]="$entry"
      done
    fi

    consumed=()
    for entry in "${provider[@]}"; do
      _dotfiles_path_contains "$entry" "${managed[@]}" && continue
      found=0
      for ((i=0; i<${#callers[@]}; i++)); do
        if [[ ${consumed[i]-} != 1 && $entry == "${callers[i]}" ]]; then
          consumed[i]=1
          found=1
          break
        fi
      done
      (( found )) || output[${#output[@]}]="$entry"
    done
    result=
    separator=
    for entry in "${output[@]}"; do
      result=$result$separator$entry
      separator=:
    done
    PATH=$result
    return 0
  }

  function _dotfiles_initialize_environment() {
    local incoming_path=$PATH prior_baseline=${_DOTFILES_PATH_BASELINE-}
    local prior_home=${_DOTFILES_PATH_HOME-} homebrew_prefix=

    export LANG=en_US.UTF-8
    export LC_ALL=en_US.UTF-8
    initialize_homebrew

# Initialize the Python version manager

    # If pyenv is installed and hasn't been initialized yet.
    if which -s pyenv && [[ -z "${PYENV_SHELL}" ]]; then
      export PYENV_VIRTUALENV_DISABLE_PROMPT=1
      eval "$(pyenv init -)"
    fi

# Initialize the Ruby Version manager

    # If rbenv is installed and hasn't been initialized yet.
    if which -s rbenv && [[ -z "${RBENV_SHELL}" ]]; then
      eval "$(rbenv init -)"
    fi


    # If n is installed and hasn't been initialized yet.
    if which -s n && [[ -z "${N_PREFIX}" ]]; then
      export N_PREFIX=$HOME/.n
      export PATH=$N_PREFIX/bin:$PATH
    fi

    NODE_MODULES_BIN=$HOME/node_modules/.bin
    BUN_BIN=$HOME/.bun/bin
    PERSONAL_BIN=$HOME/.local/bin


# V-I'm in love with your key bindings
# - rlwrap is a utility to bring the readline behavior to
#   utilities that do not support it natively.
# - See rlwrap's man pages for more info on the env vars below.
# - RLWRAP_FILTERDIR points to where my filters reside.  My filters in turn
#   use rlwrapfilter.py which resides in /usr/local/shared/rlwrap/filters/
#   which is a symbolic link into the current version of rlwrap installed via
#   Homebrew. Pointing RLWRAP_FILTERDIR there or putting my filters in that
#   directory would mean things break when brew upgrades rlwrap.

    [[ -e /usr/local/bin/vi ]] \
      && export EDITOR=/usr/local/bin/vi \
      || export EDITOR=/usr/bin/vi

    # XXX: Disabling until I review and install rlwrap again.
    #export RLWRAP_HOME=$HOME/.rlwrap
    #export RLWRAP_EDITOR="vi '+call cursor(%L, %C)'"
    ##export RLWRAP_FILTERDIR=/usr/local/share/rlwrap/filters
    #export RLWRAP_FILTERDIR=$HOME/.local/share/rlwrap/filters


# Configure env vars for Golang

    export GOPATH=$HOME/.go
    _dotfiles_rebuild_path "$incoming_path" "$PATH" "$homebrew_prefix" "$prior_baseline" "$prior_home"
    export PATH
    export _DOTFILES_PATH_BASELINE="$PATH"
    export _DOTFILES_PATH_HOME="$HOME"
  }

  _dotfiles_initialize_environment
