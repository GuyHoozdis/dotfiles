#!/usr/bin/env bash
## Dotfiles Installation Script
#
# This script installs dotfiles by creating symlinks from XDG-compliant locations
# (and traditional dotfile locations) to files in this repository.
#
# The repository can be cloned anywhere - the script detects its own location
# and creates symlinks accordingly.
#
# Usage:
#   ./install.sh [--dry-run] [--force]
#
# Options:
#   --dry-run    Show what would be done without making changes
#   --force      Overwrite existing symlinks without prompting
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

# Detect the absolute path to the repository root (where this script lives)
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# XDG Base Directory Specification
XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
XDG_DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

# Backup directory with timestamp
BACKUP_DIR="${XDG_STATE_HOME}/dotfiles/backup/$(date +%Y%m%d_%H%M%S)"

# Manifest file to track installed symlinks
MANIFEST_FILE="${XDG_STATE_HOME}/dotfiles/installed.json"

# Parse command-line arguments
DRY_RUN=false
FORCE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--force]"
            exit 1
            ;;
    esac
done

# =============================================================================
# Color Setup
# =============================================================================

if [[ -t 1 ]] && [[ -z "${NO_COLOR-}" ]] && [[ "${TERM-}" != "dumb" ]]; then
    RESET='\033[0m'
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[1;33m'
    BLUE='\033[0;34m'
    CYAN='\033[0;36m'
else
    RESET=''
    RED=''
    GREEN=''
    YELLOW=''
    BLUE=''
    CYAN=''
fi

# =============================================================================
# Helper Functions
# =============================================================================

log_info() {
    echo -e "${BLUE}[*]${RESET} $*"
}

log_success() {
    echo -e "${GREEN}[✓]${RESET} $*"
}

log_warning() {
    echo -e "${YELLOW}[!]${RESET} $*"
}

log_error() {
    echo -e "${RED}[✗]${RESET} $*"
}

log_dry_run() {
    echo -e "${CYAN}[DRY RUN]${RESET} $*"
}

# Detect operating system
detect_os() {
    case "$OSTYPE" in
        darwin*)
            echo "macos"
            ;;
        linux-gnu*)
            echo "linux"
            ;;
        *)
            echo "unknown"
            ;;
    esac
}

# Create a directory if it doesn't exist
ensure_directory() {
    local dir="$1"
    if [[ ! -d "$dir" ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            log_dry_run "Would create directory: $dir" >&2
        else
            mkdir -p "$dir"
            log_success "Created directory: $dir" >&2
        fi
    fi
}

# Backup a file or directory
backup_path() {
    local path="$1"
    local backup_path="${BACKUP_DIR}/$(basename "$path")"

    if [[ -e "$path" ]] && [[ ! -L "$path" ]]; then
        ensure_directory "$BACKUP_DIR"
        if [[ "$DRY_RUN" == true ]]; then
            log_dry_run "Would backup: $path -> $backup_path" >&2
        else
            mv "$path" "$backup_path"
            log_success "Backed up: $path -> $backup_path" >&2
        fi
        echo "$backup_path"
    fi
}

# Create a symlink, backing up existing file if needed
create_symlink() {
    local target="$1"  # Where the symlink points to (the file in the repo)
    local link="$2"    # The symlink location (in home directory)
    local backup_path=""

    # Expand ~ in paths
    target="${target/#\~/$HOME}"
    link="${link/#\~/$HOME}"

    # Check if target exists in repo
    if [[ ! -e "$target" ]]; then
        log_warning "Target does not exist, skipping: $target"
        return 1
    fi

    # Check if link already exists and points to correct target
    if [[ -L "$link" ]]; then
        local current_target
        current_target="$(readlink "$link")"
        if [[ "$current_target" == "$target" ]]; then
            log_info "Already linked: $link -> $target"
            return 0
        elif [[ "$FORCE" == true ]]; then
            if [[ "$DRY_RUN" == true ]]; then
                log_dry_run "Would remove existing symlink: $link"
            else
                rm "$link"
                log_warning "Removed existing symlink: $link"
            fi
        else
            log_warning "Symlink exists but points elsewhere: $link -> $current_target"
            log_warning "Use --force to overwrite"
            return 1
        fi
    elif [[ -e "$link" ]]; then
        # Path exists but is not a symlink - back it up
        backup_path=$(backup_path "$link")
    fi

    # Create parent directory if needed
    ensure_directory "$(dirname "$link")"

    # Create the symlink
    if [[ "$DRY_RUN" == true ]]; then
        log_dry_run "Would create symlink: $link -> $target"
    else
        ln -s "$target" "$link"
        log_success "Created symlink: $link -> $target"
    fi

    # Record in manifest
    if [[ -n "$backup_path" ]]; then
        record_manifest_entry "$link" "$target" "$backup_path"
    else
        record_manifest_entry "$link" "$target" ""
    fi
}

# Record an entry in the installation manifest
record_manifest_entry() {
    local link="$1"
    local target="$2"
    local backup="$3"

    # For now, just append to a simple text file
    # We'll make this proper JSON later
    if [[ "$DRY_RUN" != true ]]; then
        ensure_directory "$(dirname "$MANIFEST_FILE")"
        echo "$link|$target|$backup" >> "${MANIFEST_FILE}.tmp"
    fi
}

# Initialize manifest file
init_manifest() {
    if [[ "$DRY_RUN" != true ]]; then
        ensure_directory "$(dirname "$MANIFEST_FILE")"
        cat > "${MANIFEST_FILE}.tmp" <<EOF
# Dotfiles Installation Manifest
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")
# Repository: ${REPO_ROOT}
# OS: $(detect_os)
#
# Format: LINK|TARGET|BACKUP
EOF
    fi
}

# Finalize manifest file
finalize_manifest() {
    if [[ "$DRY_RUN" != true ]]; then
        mv "${MANIFEST_FILE}.tmp" "$MANIFEST_FILE"
        log_success "Installation manifest saved to: $MANIFEST_FILE"
    fi
}

# =============================================================================
# Installation Functions
# =============================================================================

install_xdg_config_directories() {
    log_info "Installing XDG config directories..."

    # Symlink entire config subdirectories
    create_symlink "${REPO_ROOT}/config/bash" "${XDG_CONFIG_HOME}/bash"
    create_symlink "${REPO_ROOT}/config/git" "${XDG_CONFIG_HOME}/git"
    create_symlink "${REPO_ROOT}/config/ipython" "${XDG_CONFIG_HOME}/ipython"
    create_symlink "${REPO_ROOT}/config/vim" "${XDG_CONFIG_HOME}/vim"
}

install_bash_init_files() {
    local os
    os=$(detect_os)

    log_info "Installing bash initialization files for ${os}..."

    if [[ "$os" == "macos" ]]; then
        # macOS uses .bash_login for login shells
        # Point directly to repo files (not through ~/.config/bash)
        create_symlink "${REPO_ROOT}/config/bash/login.bash" "${HOME}/.bash_login"
        create_symlink "${REPO_ROOT}/config/bash/logout.bash" "${HOME}/.bash_logout"

        # Remove .bashrc and .bash_profile if they exist (to avoid conflicts)
        for file in "${HOME}/.bashrc" "${HOME}/.bash_profile"; do
            if [[ -e "$file" ]] && [[ ! -L "$file" ]]; then
                backup_path "$file"
                if [[ "$DRY_RUN" != true ]]; then
                    log_warning "Backed up and removed: $file (to avoid conflicts with .bash_login)"
                fi
            fi
        done
    elif [[ "$os" == "linux" ]]; then
        # Linux typically uses .bashrc for interactive shells
        # Point directly to repo files (not through ~/.config/bash)
        create_symlink "${REPO_ROOT}/config/bash/login.bash" "${HOME}/.bashrc"
        create_symlink "${REPO_ROOT}/config/bash/logout.bash" "${HOME}/.bash_logout"

        # Also create .bash_profile to source .bashrc for login shells
        if [[ ! -e "${HOME}/.bash_profile" ]]; then
            if [[ "$DRY_RUN" == true ]]; then
                log_dry_run "Would create .bash_profile to source .bashrc"
            else
                cat > "${HOME}/.bash_profile" <<'EOF'
# Source .bashrc for login shells
if [[ -f ~/.bashrc ]]; then
    source ~/.bashrc
fi
EOF
                log_success "Created .bash_profile to source .bashrc"
            fi
        fi
    else
        log_warning "Unknown OS type: $os - skipping bash init files"
    fi
}

install_traditional_dotfiles() {
    log_info "Installing traditional dotfiles..."

    # Traditional dotfiles that don't support XDG
    create_symlink "${REPO_ROOT}/config/vimrc" "${HOME}/.vimrc"
    create_symlink "${REPO_ROOT}/config/inputrc" "${HOME}/.inputrc"
    create_symlink "${REPO_ROOT}/config/editrc" "${HOME}/.editrc"
    create_symlink "${REPO_ROOT}/config/pdbrc" "${HOME}/.pdbrc"
    create_symlink "${REPO_ROOT}/config/pythonrc" "${HOME}/.pythonrc"
    create_symlink "${REPO_ROOT}/config/editorconfig" "${HOME}/.editorconfig"
}

install_user_binaries() {
    log_info "Installing user binaries..."

    # Symlink bin directory to ~/.local/bin
    create_symlink "${REPO_ROOT}/bin" "${HOME}/.local/bin/dotfiles-bin"
}

# =============================================================================
# Main Installation
# =============================================================================

main() {
    log_info "Starting dotfiles installation..."
    log_info "Repository: ${REPO_ROOT}"
    log_info "Operating System: $(detect_os)"

    if [[ "$DRY_RUN" == true ]]; then
        log_warning "DRY RUN MODE - No changes will be made"
    fi

    # Initialize manifest
    init_manifest

    # Install different components
    install_xdg_config_directories
    install_bash_init_files
    install_traditional_dotfiles
    install_user_binaries

    # Finalize manifest
    finalize_manifest

    echo ""
    log_success "Dotfiles installation complete!"

    if [[ "$DRY_RUN" != true ]]; then
        log_info "Backups saved to: ${BACKUP_DIR}"
        log_info "Manifest saved to: ${MANIFEST_FILE}"
        echo ""
        log_warning "Please restart your shell or run: source ~/.bash_login (macOS) or source ~/.bashrc (Linux)"
    fi
}

# Run main function
main "$@"
