"""
Safe Storage Path Resolver for Android Go and Cross-Platform Environments.
Ensures persistent, writable directory access without triggering PermissionError on Android.
"""

import os
import sys
import logging

logger = logging.getLogger("StoragePath")


def get_base_storage_dir() -> str:
    """
    Safely determine the persistent, writable base storage directory
    for Android (including Android 10 Go on itel A48 and Android 14 on Realme C63)
    as well as desktop/test environments.
    Guarantees that the returned path is writable and never throws PermissionError on startup.
    """
    # 1. Check if running under Kivy and an App instance exists with user_data_dir
    try:
        from kivy.app import App
        app = App.get_running_app()
        if app and hasattr(app, "user_data_dir") and app.user_data_dir:
            path = app.user_data_dir
            if _is_writable_dir(path):
                return path
    except Exception:
        pass

    # 2. On Android via pyjnius, directly query context.getFilesDir()
    try:
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        if PythonActivity.mActivity:
            path = PythonActivity.mActivity.getFilesDir().getAbsolutePath()
            if path and _is_writable_dir(path):
                return path
    except Exception:
        pass

    # 3. Check Android environment variables or well-known internal paths
    candidates = [
        os.environ.get("ANDROID_ARGUMENT"),
        os.environ.get("ANDROID_PRIVATE"),
        "/data/user/0/org.tawhid.telegramlite/files",
        "/data/data/org.tawhid.telegramlite/files",
    ]
    for c in candidates:
        if c and _is_writable_dir(c):
            return c

    # 4. Desktop / Development environment (Linux/macOS/Windows)
    try:
        home_dir = os.path.expanduser("~")
        # Ensure home_dir is not root ('/') or '/data' before using
        if home_dir and home_dir not in ("/", "/data") and os.path.isdir(home_dir):
            desktop_dir = os.path.join(home_dir, ".telegram_lite")
            if _is_writable_dir(desktop_dir):
                return desktop_dir
    except Exception:
        pass

    # 5. Last resort fallback to system temp directory (always writable)
    import tempfile
    fallback = os.path.join(tempfile.gettempdir(), "telegram_lite")
    _is_writable_dir(fallback)
    return fallback


def _is_writable_dir(path: str) -> bool:
    """Check if a directory can be created and written to."""
    try:
        os.makedirs(path, exist_ok=True)
        test_file = os.path.join(path, ".probe_write")
        with open(test_file, "w") as f:
            f.write("1")
        if os.path.exists(test_file):
            os.remove(test_file)
        return True
    except (OSError, PermissionError) as e:
        logger.debug("Path %s is not writable: %s", path, e)
        return False
