#!/usr/bin/env bash
## Test script to validate dotfiles installation in Docker container
set -euo pipefail

PASSED=0
FAILED=0

# Color output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
RESET='\033[0m'

pass() {
    echo -e "${GREEN}✓${RESET} $*"
    PASSED=$((PASSED + 1))
}

fail() {
    echo -e "${RED}✗${RESET} $*"
    FAILED=$((FAILED + 1))
}

info() {
    echo -e "${YELLOW}→${RESET} $*"
}

# Test function
test_symlink() {
    local link="$1"
    local expected_target="$2"

    if [[ ! -L "$link" ]]; then
        fail "Symlink does not exist: $link"
        return 1
    fi

    local actual_target
    actual_target="$(readlink "$link")"

    if [[ "$actual_target" == "$expected_target" ]]; then
        pass "Symlink correct: $link -> $actual_target"
        return 0
    else
        fail "Symlink incorrect: $link -> $actual_target (expected: $expected_target)"
        return 1
    fi
}

test_file_exists() {
    local file="$1"

    if [[ -e "$file" ]]; then
        pass "File exists: $file"
        return 0
    else
        fail "File missing: $file"
        return 1
    fi
}

test_backup_exists() {
    local pattern="$1"

    if compgen -G "$pattern" > /dev/null; then
        pass "Backup found matching: $pattern"
        return 0
    else
        fail "No backup found matching: $pattern"
        return 1
    fi
}

echo "========================================="
echo "Testing Dotfiles Installation"
echo "========================================="
echo ""

# Test 1: Run install script
info "Running install.sh..."
cd /home/testuser/dotfiles
if ./install.sh; then
    pass "install.sh completed successfully"
else
    fail "install.sh failed"
    exit 1
fi

echo ""
echo "========================================="
echo "Validating Installation"
echo "========================================="
echo ""

# Test 2: Check XDG config directory symlinks
info "Checking XDG config directory symlinks..."
test_symlink "$HOME/.config/bash" "/home/testuser/dotfiles/config/bash"
test_symlink "$HOME/.config/git" "/home/testuser/dotfiles/config/git"
test_symlink "$HOME/.config/vim" "/home/testuser/dotfiles/config/vim"
test_symlink "$HOME/.config/ipython" "/home/testuser/dotfiles/config/ipython"

# Test 3: Check bash init files (Linux uses .bashrc)
info "Checking bash init files..."
test_symlink "$HOME/.bashrc" "/home/testuser/dotfiles/config/bash/login.bash"
test_symlink "$HOME/.bash_logout" "/home/testuser/dotfiles/config/bash/logout.bash"

# Test 4: Check traditional dotfiles
info "Checking traditional dotfiles..."
test_symlink "$HOME/.vimrc" "/home/testuser/dotfiles/config/vimrc"
test_symlink "$HOME/.inputrc" "/home/testuser/dotfiles/config/inputrc"
test_symlink "$HOME/.pdbrc" "/home/testuser/dotfiles/config/pdbrc"

# Test 5: Check manifest file exists
info "Checking manifest file..."
test_file_exists "$HOME/.local/state/dotfiles/installed.json"

# Test 6: Check backups were created
info "Checking backups were created..."
test_backup_exists "$HOME/.local/state/dotfiles/backup/*/.bashrc"
test_backup_exists "$HOME/.local/state/dotfiles/backup/*/.bash_logout"

# Test 7: Verify backup contents
info "Verifying backup contents..."
BACKUP_DIR=$(find "$HOME/.local/state/dotfiles/backup" -type d -mindepth 1 -maxdepth 1 | head -1)
if [[ -f "$BACKUP_DIR/.bashrc" ]]; then
    if grep -q "Original bashrc" "$BACKUP_DIR/.bashrc"; then
        pass "Backup contains original content"
    else
        fail "Backup does not contain original content"
    fi
else
    fail "Backup file not found"
fi

# Test 8: Source bash config and check it works
info "Testing bash config can be sourced..."
if bash -c "source $HOME/.bashrc" 2>&1 | grep -q "BASH_CONFIG_DIR"; then
    fail "Bash config has errors"
else
    pass "Bash config sources without errors"
fi

echo ""
echo "========================================="
echo "Testing Uninstallation"
echo "========================================="
echo ""

# Test 9: Run uninstall script
info "Running uninstall.sh..."
if ./uninstall.sh; then
    pass "uninstall.sh completed successfully"
else
    fail "uninstall.sh failed"
fi

# Test 10: Verify symlinks were removed
info "Verifying symlinks were removed..."
if [[ ! -L "$HOME/.bashrc" ]]; then
    pass "Symlink removed: .bashrc"
else
    fail "Symlink still exists: .bashrc"
fi

if [[ ! -L "$HOME/.config/bash" ]]; then
    pass "Symlink removed: .config/bash"
else
    fail "Symlink still exists: .config/bash"
fi

# Test 11: Verify original files were restored
info "Verifying original files were restored..."
if [[ -f "$HOME/.bashrc" ]] && grep -q "Original bashrc" "$HOME/.bashrc"; then
    pass "Original .bashrc was restored"
else
    fail "Original .bashrc was not restored"
fi

if [[ -f "$HOME/.bash_profile" ]] && grep -q "Original bash_profile" "$HOME/.bash_profile"; then
    pass "Original .bash_profile was restored"
else
    fail "Original .bash_profile was not restored"
fi

# Test 12: Verify manifest was removed
info "Verifying manifest was removed..."
if [[ ! -f "$HOME/.local/state/dotfiles/installed.json" ]]; then
    pass "Manifest file removed"
else
    fail "Manifest file still exists"
fi

echo ""
echo "========================================="
echo "Test Summary"
echo "========================================="
echo -e "${GREEN}Passed: $PASSED${RESET}"
echo -e "${RED}Failed: $FAILED${RESET}"
echo ""

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}All tests passed!${RESET}"
    exit 0
else
    echo -e "${RED}Some tests failed!${RESET}"
    exit 1
fi
