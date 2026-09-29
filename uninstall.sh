#!/bin/zsh
set -e
script_dir=${0:A:h}
exec /usr/bin/env python3 "$script_dir/installer.py" --uninstall "$@"
