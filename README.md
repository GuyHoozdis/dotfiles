# Another Dotfiles Repo

Work in-progress:
- Implement [XDG Base Directory Specification][xdg-base-dir-spec].
- Investigate using `stow` to [manage configuration][stow-dotfiles] files under `$HOME`.
- Decide how to handle the fact that OSX terminals are login terminals by default.
- Reconsider sourcing .local version of bash files after the standard (to allow local overrides)


## Goals

- All elements should be optional and easy to enable or revert.
- Configuration should be as minimal as possible.
- Configuration should prefer installed tools/utilities
- Access to overriden system utilities should still possible.
- It should be possible, and easy, to reset the system
  - Remove symbolic links that were created
  - Replace original files
  - Remove the cloned repo
  - Uninstall applications installed by Homebrew
  - Uninstall Homebrew


## Organization and Usage


I want to have symbolic links reference files in this repo.  Changes that
are made on the system should be committed and pushed back up to the repo.

For now; linking, backing up original files, and invoking the provisioning
scripts that install a base set of utilities are going to be a manual process.
I looked at [Dotbot][dotbot].

This repo tries to imitate the [Linux Filesystem Heirarchy Standard][fhs] to
achieve a sensible orgnization.  To that end, the repo can be cloned into
a directory named `~/.local` to achive a layout that should be familiar.



## Setting up a new system


On a brand new system:

1. Create your user
1. Install [Homebrew][homebrew]
1. Copy or create ssh keys and configure GitHub (if needed)
1. Clone this repo and ...
  - Run OSX defaults configuration (get a backup first)
  - Run base brew installation scripts
  - Run select application installation scripts
  - Link select configuration files (move originals first)



## Updating an existing system


TODO ...



# Things that are missing

... a lot, but this is a start.


Check out these references for further brew inspiration
- https://gist.github.com/kevinelliott/3135044
- https://github.com/paulirish/dotfiles
- https://github.com/mathiasbynens/dotfiles
- http://blog.apps.npr.org/2013/06/06/how-to-setup-a-developers-environment.html
- https://github.com/donnemartin/dev-setup
- https://dotfiles.github.io


[xdg-base-dir-spec]: https://specifications.freedesktop.org/basedir-spec/latest/
[stow-dotfiles]: https://brandon.invergo.net/news/2012-05-26-using-gnu-stow-to-manage-your-dotfiles.html
[homebrew]: https://brew.sh/
[dotbot]: https://github.com/anishathalye/dotbot
[fhs]: http://www.pathname.com/fhs/pub/fhs-2.3.html
