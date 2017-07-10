# The Backup Directory

Any content that would be needed to achieve an uninstall would be
stored under this directory.  The system settings can be collected
using the `defaults` utility.

    $ mkdir -p ~/.local/var/backup/osx
    $ defaults read > ~/.local/var/backup/osx/system.defaults

Original files, that get replaced by symlinks into this directory,
should also be stored here.
