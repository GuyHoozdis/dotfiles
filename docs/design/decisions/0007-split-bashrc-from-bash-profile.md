# 0007: Split per-shell startup into `.bashrc` behind a `.bash_profile` entrypoint

Date: 2026-11-12

Status: accepted and implemented.

## Context

The only managed entrypoint was `etc/bash_login.bash`, linked by hand as
`~/.bash_login`. Bash reads it only for login shells, so an interactive
non-login child (plain `bash`) had none of the user functions, such as
`codetree` and `jqless`, that open question S2 requires. Running the whole
loader in every child would also reinitialize PATH. That would conflict with
[decision 0003](0003-preserve-caller-path-overrides.md) for callers that
prepend PATH entries.

Bash on macOS and Linux both read `~/.bash_profile` first among login files.
Ubuntu's skeleton `.profile` and a stale `.bash_login` are ignored when it
exists.

## Decision

- `etc/bash_profile.bash`, linked as `~/.bash_profile`, is the login
  entrypoint. It loads `exports` (with its `.local` override first), then
  sources `~/.bashrc`. It does not source `~/.profile`.
- `etc/bashrc.bash`, linked as `~/.bashrc`, returns early for non-interactive
  shells. Otherwise it loads `aliases`, `functions`, `app-config`, and `prompt`,
  each with its `.local` override first. It does not touch PATH or exported
  environment, so a child keeps what it inherited.
- `etc/bash_login.bash` is retired.

## Alternatives

- Keep `.bash_login` and add `.bashrc`: works, but keeps a less conventional
  entrypoint that `.bash_profile` silently shadows if one is ever created.
- Run the full loader from `.bashrc`: makes functions available, but
  reinitializes PATH in every child shell.
- Source `.profile` from `.bash_profile`: would pull in distribution defaults
  (for example Ubuntu adding `~/bin`) that this configuration does not manage.

## Consequences

- Interactive non-login shells get functions, aliases, and the prompt while
  keeping their inherited PATH. Verified on both pinned Tart guests.
- Non-interactive login shells (`bash -l -c ...`) no longer load aliases,
  functions, or the prompt.
- Each module loads once per login shell, with `.local` first.
- Ubuntu's skeleton `.profile` is intentionally ignored.
- Per-shell settings (`shopt`, `bind`, history variables) now live in
  `shell-options.bash` and are loaded for interactive shells.
- Known limitations, left as follow-ups:
  - `exports.local.bash` remains login-only.
  - pyenv and rbenv init is guarded by exported `PYENV_SHELL`/`RBENV_SHELL`,
    so their shell functions are absent in non-login children.
  - `jqless` and `pyenv-venv-reset` pick their definitions with `which -s`
    against the inherited PATH at startup.
- Existing installs must migrate by hand:

  ```bash
  ln -s ~/dotfiles/etc/bash_profile.bash ~/.bash_profile
  ln -s ~/dotfiles/etc/bashrc.bash ~/.bashrc
  rm ~/.bash_login
  ```

  Check first that `~/.bash_profile` and `~/.bashrc` do not already exist.

## Source

User statements in the originating conversation, 2026-11-12:
"I approve." and "I'd like to move away from `.bash_login` as I have been using
and use `.bash_profile` in its place. I think this will help consistent
behavior across OSX and Linux platforms."

Confirming the non-interactive consequence, the same day: "I will never want to
do something like `bash -c 'codetree'` nor `bash -l -c 'codetree'` nor anything
of similar intent - to run my own functions non-interactively."
