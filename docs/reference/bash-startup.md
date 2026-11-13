# Bash startup files

## Two independent properties

A shell can be login or non-login, and interactive or non-interactive.
Login does not mean "first shell," and a subshell is not necessarily non-login.
These rules apply to Bash on both macOS and Linux; launchers and system files
can differ.

- Interactive: `$-` contains `i` ([testing interactivity](https://www.gnu.org/software/bash/manual/html_node/Is-this-Shell-Interactive_003f.html#Is-this-Shell-Interactive_003f-1)).
  `bash -i` explicitly requests this ([interactive shell definition](https://www.gnu.org/software/bash/manual/html_node/What-is-an-Interactive-Shell_003f.html#What-is-an-Interactive-Shell_003f-1)).
- Login: `shopt -q login_shell` succeeds. `bash -l` requests this.
- `SHLVL` is neither an interactivity test nor a reliable initialization guard.

The examples below assume normal Bash invocation, not Bash named `sh`, POSIX
mode, privileged invocation, or explicitly sourced files.

## Which files are read?

| Invocation | Automatic startup files |
|------------|-------------------------|
| `bash` from a terminal | `~/.bashrc` (interactive, non-login) |
| `bash -l` from a terminal | `/etc/profile`, then the first readable user login file below |
| `bash -i` | `~/.bashrc` |
| `bash -il` | `/etc/profile`, then the first readable user login file |
| `bash -c 'command'` | The file named by exported `BASH_ENV`, if set; not the ordinary profile/rc files |
| `bash script.sh` | The file named by exported `BASH_ENV`, if set |
| `bash -lc 'command'` | Login files, plus `BASH_ENV` processing for the non-interactive shell |

For login shells, the [documented user-file search order](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html#Invoked-as-an-interactive-login-shell_002c-or-with-_002d_002dlogin)
is:

1. `~/.bash_profile`
2. `~/.bash_login`
3. `~/.profile`

Bash reads **only the first readable file**, not all three. If all three exist
and are readable, `.bash_profile` wins; `.bash_login` and `.profile` are skipped.
An empty but readable `.bash_profile` still wins.

An interactive login shell does **not** automatically read `~/.bashrc`.
Interactive non-login Bash does **not** automatically read `.bash_profile`,
`.bash_login`, or `.profile`.

System startup files can source additional files. For example, the observed
macOS `/etc/profile` runs `path_helper` and sources `/etc/bashrc`. Linux
distributions may have system Bash rc files and distribution-specific behavior.
An application's shell integration can also explicitly source files.
The standalone [macOS terminal integration synopsis](macos-terminal-startup.md)
details `/etc/bashrc_$TERM_PROGRAM` dispatch and Apple Terminal's hooks.

The table follows the GNU manual's sections on
[interactive non-login startup](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html#Invoked-as-an-interactive-non_002dlogin-shell)
and [non-interactive startup (`BASH_ENV`)](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html#Invoked-non_002dinteractively),
in addition to the login rules linked above.

## Intended responsibilities

| File | Typical responsibility |
|------|------------------------|
| `/etc/profile` | Administrator/distribution login environment; not managed by a personal dotfiles installer |
| `~/.bash_profile` | Bash login entrypoint; environment setup and explicit dispatch to interactive configuration |
| `~/.bash_login` | Alternative Bash login entrypoint with lower priority, not an additional startup phase |
| `~/.profile` | Portable login environment for shells that use it; keep shared content POSIX-compatible |
| `~/.bashrc` | Per-interactive-Bash aliases, functions, prompt, completion, history, and shell options |
| `~/.bash_logout` | Login-shell exit cleanup |
| File named by `BASH_ENV` | Explicitly opted-in non-interactive Bash configuration; not a way to load the full interactive framework into every script |
| `~/.inputrc` | Readline configuration, including vi bindings; not a Bash shell script |

These are conventions layered on the automatic selection rules. Bash does not
enforce which kind of setting goes in a file.

## Is sourcing `.bashrc` from `.bash_profile` proper?

Yes. The [GNU Bash manual explicitly describes sourcing `.bashrc` from
`.bash_profile`](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html#Invoked-as-an-interactive-non_002dlogin-shell).
The following adaptation adds an interactive guard and checks readability; it is
not a verbatim copy of the manual's example:

```bash
if [[ $- == *i* && -r "$HOME/.bashrc" ]]; then
  source "$HOME/.bashrc"
fi
```

In this example, the interactive check deliberately avoids loading interactive
configuration for `bash -lc`. `.bashrc` should also guard its interactive content
because it can be sourced explicitly or through remote-shell startup behavior.

Keep the dependency one-way: login entrypoint -> `.bashrc` -> interactive
modules. Do not have `.bashrc` source a login file that sources `.bashrc` again.
Environment helpers can be shared separately and must tolerate repeated use.

If `.bash_profile` is introduced into an existing `.bash_login` installation,
its higher priority must be handled deliberately or the old framework will stop
loading. Renaming a file is not required merely to correct PATH.

## Important exceptions and controls

- `--noprofile` disables automatic login-profile loading.
- `--norc` disables automatic interactive `.bashrc` loading. It does not prevent
  a profile from explicitly sourcing `.bashrc`.
- `--rcfile file` replaces the automatic interactive non-login rc file; it does
  not replace a login profile. Combining it with `--login` does not cause Bash
  to use that file as its login entrypoint.
- [Non-interactive Bash started by a remote shell daemon](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html#Invoked-by-remote-shell-daemon)
  may read `.bashrc`.
  This is why interactive-only commands must be guarded and remote startup must
  not print unsolicited output. SSH startup also depends on the remote login
  shell and server configuration.
- [Bash invoked as `sh`](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html#Invoked-with-name-sh)
  uses different rules: login startup reads `/etc/profile`
  and `~/.profile`; interactive non-login startup uses `ENV`, not `.bashrc`.
- [Bash in POSIX mode](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html#Invoked-in-POSIX-mode)
  uses `ENV` for interactive startup.
- Interactive login exit reads `.bash_logout`; non-interactive login Bash reads
  it when executing the `exit` builtin.
- `( commands )` is a subshell environment, not a fresh Bash invocation; it does
  not rerun startup files.

## Implications for this repository

`etc/bash_login.bash` currently loads the framework, while the initial metadata
check found no `~/.bashrc` entry. `etc/bashrc.d/prompt.bash:217` exports
`PROMPT_COMMAND=set_prompt`. A new interactive non-login Bash can therefore
inherit the hook without loading `set_prompt` and its helpers.

Load prompt functions in each interactive shell before installing the prompt
hook. Do not solve this by exporting the entire function namespace. Whether the
hook remains exported should be decided with launcher integration in mind.

Environment inheritance does not eliminate per-shell initialization: aliases,
ordinary functions, completion registrations, and most shell options are not
inherited like exported environment variables. Conversely, reloading those
settings must not repeatedly duplicate or scramble PATH.

Bash does not automatically discover startup files in `~/.config/bash`.
An XDG-oriented layout still needs traditional home-directory entrypoint shims
or another explicit launcher arrangement.

## Sources

Authoritative GNU documentation, consulted 2026-11-10:

- [Bash startup files](https://www.gnu.org/software/bash/manual/html_node/Bash-Startup-Files.html#Bash-Startup-Files-1)
- [What is an interactive shell?](https://www.gnu.org/software/bash/manual/html_node/What-is-an-Interactive-Shell_003f.html#What-is-an-Interactive-Shell_003f-1)
- [Testing interactivity](https://www.gnu.org/software/bash/manual/html_node/Is-this-Shell-Interactive_003f.html#Is-this-Shell-Interactive_003f-1)
