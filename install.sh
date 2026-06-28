#!/bin/bash
set -e

echo "========================================="
echo "  Chip Agent - Quick Install"
echo "========================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found. Install Python 3.10+ first."
    exit 1
fi

# Check pip
if ! command -v pip3 &> /dev/null && ! command -v pip &> /dev/null; then
    echo "Error: pip not found. Install pip first."
    exit 1
fi

# Clone or update repo
INSTALL_DIR="${CHIP_INSTALL_DIR:-$HOME/.chip}"

if [ -d "$INSTALL_DIR" ]; then
    echo "Updating Chip in $INSTALL_DIR..."
    cd "$INSTALL_DIR"
    git pull
else
    echo "Cloning Chip to $INSTALL_DIR..."
    git clone https://github.com/igord3000/chip.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Install dependencies
echo "Installing dependencies..."
pip3 install -e . 2>/dev/null || pip install -e .

# Run setup
echo ""
echo "Running Chip setup..."
python3 -m chip setup

echo ""
echo "========================================="
echo "  Installation complete!"
echo "========================================="
echo ""
echo "Usage:"
echo "  chip run \"your task here\""
echo ""
echo "Examples:"
echo "  chip run \"Напиши hello world на Python\""
echo "  chip run \"Создай веб-сервер на Flask\""
echo "  chip run --model qwen3:14b \"Проанализируй код\""
echo ""
