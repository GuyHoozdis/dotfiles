# macOS Bash terminal integration

Synopsis of the local macOS 26.7.1 system files, inspected 2026-11-10 without
sourcing them. This describes the installed implementation, not a promise about
every macOS version. System file links below refer to this machine; line
references are provided because local-file line fragments are editor-dependent.

## System startup routing

The observed chain is:

```text
login Bash
  /etc/profile
    path_helper
    /etc/bashrc
      return if PS1 is empty
      set default PS1; enable checkwinsize
      source readable /etc/bashrc_$TERM_PROGRAM
  first readable user login file
```

Sources: [`/etc/profile`](file:///etc/profile), lines 3-9, and
[`/etc/bashrc`](file:///etc/bashrc), lines 1-10.

Thus `TERM_PROGRAM=Apple_Terminal` selects
[`/etc/bashrc_Apple_Terminal`](file:///etc/bashrc_Apple_Terminal).
This is explicit shell-script dispatch, not a Bash builtin or an instruction to
source every `/etc/bashrc_*` file. A readable matching file must exist.

The early guard uses `PS1`, not `$-`. Its intent is interactive-only setup;
unusual callers that manually set/unset PS1 can affect that check. See GNU's
[interactivity tests](https://www.gnu.org/software/bash/manual/html_node/Is-this-Shell-Interactive_003f.html#Is-this-Shell-Interactive_003f-1).
The terminal-specific script itself relies on this routing guard.

This chain establishes what happens through the system login profile. Do not
infer from it that every non-login Bash automatically reads `/etc/bashrc`;
see the [Bash startup reference](bash-startup.md#which-files-are-read).

## Working-directory reporting

Source: `/etc/bashrc_Apple_Terminal`, lines 8-36.

Unless `INSIDE_EMACS` is set, the script defines `update_terminal_cwd` and
prepends it to the existing scalar `PROMPT_COMMAND`. At each prompt it emits an
OSC 7 terminal escape sequence containing a `file://hostname/path` URL.

It percent-encodes the working-directory pathname byte-by-byte, using local
locale settings so multibyte characters and spaces are encoded rather than
inserted into the URL raw. Including the hostname distinguishes paths on
different hosts.

This lets a supporting terminal track the shell's current directory for features
such as directory-aware new sessions or restoration. It is not a PATH change,
does not change directories, and does not by itself implement full shell
integration or remote-host browsing.

## Terminal Resume session state

Source: `/etc/bashrc_Apple_Terminal`, lines 39-108 and 211-243.

Session setup runs when:

- `SHELL_SESSION_DID_INIT` is zero/unset;
- `TERM_SESSION_ID` is nonempty;
- `~/.bash_sessions_disable` does not exist.

The initialization marker is shell-local in this script, not explicitly
exported. It prevents repeated setup in the same shell; it is not a general
child-shell initialization policy.

The script creates `~/.bash_sessions` with requested mode 0700 and derives a
session filename from `TERM_SESSION_ID`. If a readable saved session file exists,
it sources that file and then removes it. Saved state is executable shell
restoration code, not just serialized data.

On exit it writes a restoration message to the session file and calls an
optional `shell_session_save_user_state` function. That hook may append commands
to restore user-selected state. It does not automatically snapshot all variables,
aliases, functions, or PATH.

The script registers `shell_session_update` with an `EXIT` trap. That function
saves session state and then attempts expiration cleanup. A later replacement
of the EXIT trap can prevent this work; this implementation is not a generic
trap-composition framework.

## Per-session and shared history

Source: `/etc/bashrc_Apple_Terminal`, lines 111-205.

The optional history layer tracks three files: a session's accumulated history,
its newly entered commands, and the original shared `HISTFILE`.

- When an existing nonempty session history is found, it reads that history and
  switches new history recording to the session's intermediate file.
- For a new session, it schedules a one-time `shell_session_history_check` in
  `PROMPT_COMMAND`. Deferring the decision allows user startup files to set their
  history preferences first.
- At save time it appends new entries to both session and shared histories,
  seeds session history from shared history if needed, and attempts to enforce
  `HISTFILESIZE`.

The history policy defaults off when `histappend` is enabled or `HISTTIMEFORMAT`
is nonempty, unless `SHELL_SESSION_HISTORY=1` explicitly opts in.
`SHELL_SESSION_HISTORY=0` disables per-session history, not the entire session
state mechanism. Creating `~/.bash_sessions_disable` disables session setup,
but does not disable the separate working-directory reporting hook.

It writes progress/restoration messages to the terminal. It is not a quiet,
generic history synchronizer for automation.

One implementation detail warrants caution before imitation: line 201 assigns
`HISTFILESIZE="$size"`, although no local `size` assignment is visible in the
inspected script. We have not executed or diagnosed that behavior; do not copy
the truncation logic on the assumption that it is a portable reference.

## Retention and filesystem behavior

Source: `/etc/bashrc_Apple_Terminal`, lines 213-243.

Session writes use `umask 077`. Expiration is attempted at most roughly once
per day, guarded by a timestamp and `/usr/bin/shlock`, and deletes old files
under the session directory using a two-week age threshold.

The implementation depends on macOS/BSD command behavior, including `date -r`,
`find` time units, and `shlock`. It uses absolute executable paths for exit work
so later user PATH changes do not redirect those commands. The source also uses
PATH-resolved commands during some earlier setup/restore steps; this is not
complete isolation from user configuration.

## Interaction with this repository

`etc/bashrc.d/prompt.bash:217` assigns and exports
`PROMPT_COMMAND=set_prompt`, replacing both Apple prompt callbacks if present:

- Working-directory updates stop running through that hook.
- The deferred first-prompt history decision is lost. Apple's exit-time history
  eligibility check still exists, so overwriting the hook does not necessarily
  disable every history-save path.

`etc/bashrc.d/exports.bash` enables `histappend` and sets `HISTTIMEFORMAT`, both
of which make Apple's per-session history default off for a new session.
Restored-session handling happens earlier and is a distinct branch; do not assume
these later settings prevent every earlier history operation.

The repository's prompt file already comments on disliking history reloads that
interleave other shells' commands. Reproducing Apple's history layer is therefore
not an obvious improvement.

## What is worth borrowing?

| Pattern | Recommendation |
|---------|----------------|
| Compose prompt callbacks instead of replacing existing hooks | Yes: preserve terminal/IDE hooks while installing our prompt; registration should be repeat-safe and compatible with the supported Bash versions |
| Terminal-specific adapter dispatch | Useful: keep optional terminal integrations outside core PATH logic; use guarded, explicit supported adapters rather than automatically sourcing arbitrary names from a user-controlled variable |
| Working-directory reporting | Preserve existing integration first; add our own only if a supported terminal lacks it, avoiding duplicate escape sequences |
| Deferred interactive setup | Useful when behavior depends on user settings established later; not a reason to defer or repeatedly rebuild PATH |
| Private state directories and intentional retention | Useful if we later own persistent state; choose appropriate XDG state locations for our code rather than copying Apple's path |
| Session/history restore machinery | Defer: Terminal-specific, side-effectful, and overlapping with existing preferences |
| Absolute executable paths for exit cleanup | Understand the intent, but do not transplant macOS paths into cross-platform code |

These are investigation recommendations, not new implementation approvals.
Nothing in this script solves caller-prepended PATH preservation.

## Fixture implications

Model pre-existing prompt callbacks and an EXIT trap with harmless markers.
Verify that candidate interactive startup preserves those hooks without
duplicating them on repeated sourcing. Testing actual prompt callback execution
requires a prompt-driving check, not just inspecting function definitions.

Do not source Apple's script in the default controlled suite: it can source saved
session code, create files, install an exit trap, and delete expired state.
Build a minimal simulation of the relevant hook contracts; any real-system
integration remains separate and opt-in.
