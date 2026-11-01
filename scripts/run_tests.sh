#!/usr/bin/env bash
set -e

# If pytest is not in current PATH, try standard venv paths
if ! command -v pytest >/dev/null 2>&1; then
    if [ -f "/root/venv/bin/pytest" ]; then
        export PATH="/root/venv/bin:$PATH"
    elif [ -f "$HOME/.venv/bin/pytest" ]; then
        export PATH="$HOME/.venv/bin:$PATH"
    fi
fi

echo "=== Running Telegram Lite Automated Test Suite ==="

# Ensure headless virtual display is available if running on headless Linux
if [ -z "$DISPLAY" ]; then
    if command -v xvfb-run >/dev/null 2>&1; then
        echo "Using xvfb-run for virtual display..."
        xvfb-run -s "-screen 0 1024x768x24" pytest -v tests/
    else
        echo "Running pytest with mock window..."
        KIVY_WINDOW=mock pytest -v tests/
    fi
else
    pytest -v tests/
fi

echo "=== All Tests Passed Successfully! ==="
