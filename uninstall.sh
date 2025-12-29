#!/usr/bin/env bash
## Dotfiles Uninstallation Script
#
# This script removes symlinks created by install.sh and restores backed up files.
# It uses the installation manifest to know what to remove.
#
# Usage:
#   ./uninstall.sh [--dry-run] [--keep-backups]
#
# Options:
#   --dry-run        Show what would be done without making changes
#   --keep-backups   Don't delete backup files after restoration
#

set -euo pipefail

# =============================================================================
# Configuration
# =============================================================================

# XDG Base Directory Specification
XDG_STATE_HOME="${XDG_STATE_HOME:-$HOME/.local/state}"

# Manifest file location
MANIFEST_FILE="${XDG_STATE_HOME}/dotfiles/installed.json"

# Parse command-line arguments
DRY_RUN=false
KEEP_BACKUPS=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --keep-backups)
            KEEP_BACKUPS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--dry-run] [--keep-backups]"
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

# Remove a symlink if it exists
remove_symlink() {
    local link="$1"

    if [[ -L "$link" ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            log_dry_run "Would remove symlink: $link"
        else
            rm "$link"
            log_success "Removed symlink: $link"
        fi
        return 0
    elif [[ -e "$link" ]]; then
        log_warning "Not a symlink, skipping: $link"
        return 1
    else
        log_info "Symlink doesn't exist, skipping: $link"
        return 0
    fi
}

# Restore a backed up file
restore_backup() {
    local backup="$1"
    local original="$2"

    if [[ ! -e "$backup" ]]; then
        log_info "No backup found at: $backup"
        return 1
    fi

    # Make sure the target location doesn't exist
    if [[ -e "$original" ]] && [[ ! -L "$original" ]]; then
        log_warning "Target exists and is not a symlink: $original"
        log_warning "Not restoring backup to avoid overwriting"
        return 1
    fi

    # Remove symlink if it exists
    if [[ -L "$original" ]]; then
        if [[ "$DRY_RUN" == true ]]; then
            log_dry_run "Would remove symlink before restore: $original"
        else
            rm "$original"
        fi
    fi

    # Restore the backup
    if [[ "$DRY_RUN" == true ]]; then
        log_dry_run "Would restore backup: $backup -> $original"
    else
        mv "$backup" "$original"
        log_success "Restored backup: $backup -> $original"
    fi
}

# Remove empty parent directories
cleanup_empty_dirs() {
    local dir="$1"

    # Don't remove if it doesn't exist or is not a directory
    if [[ ! -d "$dir" ]]; then
        return 0
    fi

    # Don't remove if directory is not empty
    if [[ -n "$(ls -A "$dir" 2>/dev/null)" ]]; then
        return 0
    fi

    # Remove empty directory
    if [[ "$DRY_RUN" == true ]]; then
        log_dry_run "Would remove empty directory: $dir"
    else
        rmdir "$dir" 2>/dev/null || true
        log_success "Removed empty directory: $dir"
    fi

    # Recursively check parent directory
    local parent
    parent="$(dirname "$dir")"
    if [[ "$parent" != "$HOME" ]] && [[ "$parent" != "/" ]]; then
        cleanup_empty_dirs "$parent"
    fi
}

# =============================================================================
# Uninstallation Functions
# =============================================================================

uninstall_from_manifest() {
    log_info "Reading installation manifest: $MANIFEST_FILE"

    if [[ ! -f "$MANIFEST_FILE" ]]; then
        log_error "Manifest file not found: $MANIFEST_FILE"
        log_error "Cannot proceed with uninstallation"
        exit 1
    fi

    local line_count=0
    local removed_count=0
    local restored_count=0
    local backup_dir=""

    # Read manifest file line by line
    while IFS='|' read -r link target backup; do
        # Skip comments and empty lines
        [[ "$link" =~ ^#.*$ ]] && continue
        [[ -z "$link" ]] && continue

        line_count=$((line_count + 1))

        log_info "Processing: $link"

        # Remove symlink
        if remove_symlink "$link"; then
            removed_count=$((removed_count + 1))
        fi

        # Restore backup if it exists
        if [[ -n "$backup" ]] && [[ "$backup" != "" ]]; then
            # Extract backup directory from first backup path
            if [[ -z "$backup_dir" ]]; then
                backup_dir="$(dirname "$backup")"
            fi

            if restore_backup "$backup" "$link"; then
                restored_count=$((restored_count + 1))
            fi
        fi

        # Clean up empty parent directories
        cleanup_empty_dirs "$(dirname "$link")"
    done < "$MANIFEST_FILE"

    log_success "Processed $line_count entries from manifest"
    log_success "Removed $removed_count symlinks"
    log_success "Restored $restored_count backups"

    # Remove manifest file
    if [[ "$DRY_RUN" == true ]]; then
        log_dry_run "Would remove manifest file: $MANIFEST_FILE"
    else
        rm "$MANIFEST_FILE"
        log_success "Removed manifest file: $MANIFEST_FILE"
    fi

    # Remove backup directory if it's empty and --keep-backups is not set
    if [[ -n "$backup_dir" ]] && [[ "$KEEP_BACKUPS" == false ]]; then
        if [[ -d "$backup_dir" ]] && [[ -z "$(ls -A "$backup_dir" 2>/dev/null)" ]]; then
            if [[ "$DRY_RUN" == true ]]; then
                log_dry_run "Would remove empty backup directory: $backup_dir"
            else
                rmdir "$backup_dir"
                log_success "Removed empty backup directory: $backup_dir"
            fi
        elif [[ -d "$backup_dir" ]]; then
            log_info "Backup directory not empty, keeping: $backup_dir"
        fi
    elif [[ "$KEEP_BACKUPS" == true ]]; then
        log_info "Keeping backup directory: $backup_dir"
    fi
}

# Remove additional files created by install script
cleanup_additional_files() {
    log_info "Checking for additional files to clean up..."

    # Remove .bash_profile if it was created by install script for Linux
    local bash_profile="${HOME}/.bash_profile"
    if [[ -f "$bash_profile" ]]; then
        # Check if it's the file we created (contains our marker comment)
        if grep -q "Source .bashrc for login shells" "$bash_profile" 2>/dev/null; then
            if [[ "$DRY_RUN" == true ]]; then
                log_dry_run "Would remove generated .bash_profile: $bash_profile"
            else
                rm "$bash_profile"
                log_success "Removed generated .bash_profile: $bash_profile"
            fi
        fi
    fi
}

# =============================================================================
# Main Uninstallation
# =============================================================================

main() {
    log_info "Starting dotfiles uninstallation..."

    if [[ "$DRY_RUN" == true ]]; then
        log_warning "DRY RUN MODE - No changes will be made"
    fi

    # Uninstall based on manifest
    uninstall_from_manifest

    # Clean up additional files
    cleanup_additional_files

    echo ""
    log_success "Dotfiles uninstallation complete!"

    if [[ "$DRY_RUN" != true ]]; then
        log_info "Your system has been restored to its pre-installation state"
        log_info "Homebrew packages and other installed software were left untouched"
        echo ""
        log_warning "Please restart your shell for changes to take effect"
    fi
}

# Run main function
main "$@"
