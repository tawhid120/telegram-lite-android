#!/usr/bin/env bash
set -e

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
