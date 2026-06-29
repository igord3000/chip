#!/bin/bash
# Chip launcher script - rebuilds and runs

cd /mnt/c/Users/user/chip

# Reinstall
pip install -e . -q 2>/dev/null

# Run chip
exec chip "$@"
