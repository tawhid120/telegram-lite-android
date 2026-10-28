#!/usr/bin/env bash
set -e

echo "=== Building Telegram Lite Android APK ==="

# 1. Run tests first
./scripts/run_tests.sh

# 2. Check Java
if ! command -v java >/dev/null 2>&1; then
    echo "ERROR: Java is not installed. Please install OpenJDK 17."
    exit 1
fi
echo "Java version:"
java -version 2>&1 | head -n 2

# 3. Check Buildozer
if ! command -v buildozer >/dev/null 2>&1; then
    echo "ERROR: Buildozer is not installed. Run: pip install buildozer cython"
    exit 1
fi

# 4. Trigger Buildozer APK build
echo "Running Buildozer Android Debug build..."
buildozer -v android debug

# 5. Verify output APK
echo "Verifying generated APK in bin/..."
APK_FILE=$(find bin/ -type f -name "*.apk" | head -n 1)
if [ -z "$APK_FILE" ]; then
    echo "ERROR: No APK found in bin/."
    exit 1
fi

FILE_SIZE=$(stat -c%s "$APK_FILE")
echo "✓ APK built successfully: $APK_FILE"
echo "✓ APK file size: $((FILE_SIZE / 1024 / 1024)) MB ($FILE_SIZE bytes)"
sha256sum "$APK_FILE"
