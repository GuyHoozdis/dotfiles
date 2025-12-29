# Another Dotfiles Repo

[![Test Installation](https://github.com/guyhoozdis/dotfiles/actions/workflows/test.yml/badge.svg)](https://github.com/guyhoozdis/dotfiles/actions/workflows/test.yml)

Modern, XDG-compliant dotfiles with automated installation and backup.

## Features

- **XDG Base Directory compliant** - Uses `~/.config/`, `~/.local/`, and `~/.local/state/`
- **Automated installation** - Single command setup with `install.sh`
- **Automatic backups** - Existing files are backed up before symlinking
- **Easy uninstall** - Restore your system to its original state with `uninstall.sh`
- **Cross-platform** - Supports both macOS and Linux
- **Repository location agnostic** - Clone anywhere, symlinks handle the rest


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


## Organization

This repository follows the [XDG Base Directory Specification][xdg-base-dir-spec]:

```
dotfiles/
├── config/              # User configuration files → ~/.config/*
│   ├── bash/           # Bash configuration (modular)
│   ├── git/            # Git configuration
│   ├── vim/            # Vim configuration
│   ├── ipython/        # IPython profiles
│   └── ...
├── bin/                # User executables → ~/.local/bin/dotfiles-bin
├── share/              # Shared data
│   ├── install/        # Installation scripts (Homebrew, macOS defaults, etc.)
│   └── python/         # Python project templates
└── state/              # State data (backups, examples)
    ├── backup/         # Backup of original files
    └── examples/       # Example configurations
```

The install script creates symlinks from XDG-compliant locations to files in this repository.
This means you can edit configs in the repo and see changes immediately, making it easy to
track modifications with `git status` and commit them back.



## Quick Start

### Installation

```bash
# Clone the repository (can be anywhere)
git clone https://github.com/guyhoozdis/dotfiles ~/Development/guyhoozdis/dotfiles
cd ~/Development/guyhoozdis/dotfiles

# Preview what will be installed (dry-run mode)
./install.sh --dry-run

# Install dotfiles (creates symlinks, backs up existing files)
./install.sh

# Restart your shell
exec bash --login
```

The install script will:
1. Detect your operating system (macOS or Linux)
2. Back up existing dotfiles to `~/.local/state/dotfiles/backup/TIMESTAMP/`
3. Create symlinks from XDG locations (`~/.config/*`, `~/.bash_login`, etc.) to the repo
4. Save a manifest for easy uninstallation

### Uninstallation

```bash
# Preview what will be removed (dry-run mode)
./uninstall.sh --dry-run

# Uninstall dotfiles (removes symlinks, restores backups)
./uninstall.sh

# Keep backup files after uninstall
./uninstall.sh --keep-backups
```

The uninstall script will:
1. Remove all symlinks created by the install script
2. Restore original files from backups
3. Clean up empty directories
4. Leave Homebrew packages untouched

## Setting up a new system

On a brand new system:

1. **Create your user account**

2. **Install [Homebrew][homebrew]**
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

3. **Set up SSH keys and GitHub access** (if needed)
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   # Add the public key to GitHub
   ```

4. **Clone and install dotfiles**
   ```bash
   mkdir -p ~/Development/guyhoozdis
   git clone git@github.com:guyhoozdis/dotfiles ~/Development/guyhoozdis/dotfiles
   cd ~/Development/guyhoozdis/dotfiles
   ./install.sh
   ```

5. **Optional: Install Homebrew packages and configure macOS**
   ```bash
   # Install core command-line tools
   ./share/install/homebrew/core.sh

   # Install GUI applications (macOS)
   ./share/install/homebrew/cask.sh

   # Configure macOS defaults (back up first!)
   defaults read > ~/macos-defaults-backup.plist
   ./share/install/osx/configure.sh
   ```

## Updating dotfiles

Since your dotfiles are symlinked to the repository, any changes you make to configuration
files are immediately reflected in the repo:

```bash
# Navigate to your dotfiles repo
cd ~/Development/guyhoozdis/dotfiles

# Check what's changed
git status
git diff

# Commit and push changes
git add -p
git commit -m "Update bash aliases"
git push
```

To pull updates from the remote repository:

```bash
cd ~/Development/guyhoozdis/dotfiles
git pull
# Changes are immediately active (no need to reinstall)
```



## Configuration Highlights

### Bash
- Modular configuration in `config/bash/` (aliases, functions, exports, prompt, app-config)
- Vi keybindings via `.inputrc`
- Support for local overrides (`*.local.bash` files, not committed)
- Rich command history with timestamps

### Git
- Custom aliases and configurations
- Global ignore patterns
- Git attributes for better diffs

### Python
- IPython with custom profiles and startup scripts
- Vi keybindings in Python REPL
- pdb configuration
- Project templates in `share/python/`

### Vim
- Native package manager
- Filetype-specific configurations
- Minimal but functional setup

## Development

### Adding New Configurations

1. Add the configuration file to the appropriate location in `config/`
2. Edit `install.sh` to create a symlink for the new file (if needed)
3. Test with `./install.sh --dry-run`
4. Commit and push

### Testing Changes

```bash
# Test install without making changes
./install.sh --dry-run

# Test uninstall without making changes
./uninstall.sh --dry-run

# Run comprehensive test suite in Docker
docker build -f Dockerfile.test -t dotfiles-test .
docker run --rm dotfiles-test /home/testuser/dotfiles/test-install.sh
```

### Continuous Integration

This repository uses GitHub Actions to automatically test the installation and uninstallation scripts on every push and pull request. The CI pipeline:

- Tests on both **Ubuntu (latest)** and **macOS (latest)**
- Creates dummy existing dotfiles to test backup functionality
- Runs install script and verifies:
  - All symlinks are created correctly
  - Backups are created for existing files
  - Manifest file is generated
  - Bash config can be sourced without errors
- Runs uninstall script and verifies:
  - All symlinks are removed
  - Original files are restored from backups
  - Manifest is cleaned up

The build status badge at the top of this README shows the current test status.

## Inspiration

Check out these excellent dotfile repositories:
- https://gist.github.com/kevinelliott/3135044
- https://github.com/paulirish/dotfiles
- https://github.com/mathiasbynens/dotfiles
- http://blog.apps.npr.org/2013/06/06/how-to-setup-a-developers-environment.html
- https://github.com/donnemartin/dev-setup
- https://dotfiles.github.io

## License

Public domain - use however you like.

---

[xdg-base-dir-spec]: https://specifications.freedesktop.org/basedir-spec/latest/
[homebrew]: https://brew.sh/
