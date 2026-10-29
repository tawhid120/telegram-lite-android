[app]

# (str) Title of your application
title = Telegram Lite

# (str) Package name
package.name = telegramlite

# (str) Package domain (needed for android/ios packaging)
package.domain = org.tawhid

# (str) Source code where the main.py lives
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,json

# (list) List of inclusions using pattern matching
source.include_patterns = assets/*,app/*,storage/*,telegram_client/*,recipes/*

# (list) Source files to exclude (let empty to not exclude anything)
source.exclude_exts = spec,tmp,log

# (list) List of directory to exclude (let empty to not exclude anything)
source.exclude_dirs = tests,bin,.buildozer,.github,docs,scripts,.pytest_cache

# (str) Application versioning
version = 0.1.0

# (list) Application requirements
# comma separated e.g. requirements = sqlite3,kivy
requirements = python3,kivy==2.3.1,pyjnius,sqlite3,openssl,telethon,pyaes,rsa,pyasn1,certifi,chardet,idna,requests,urllib3,filetype,six

# (str) Presplash of the application
presplash.filename = %(source.dir)s/assets/presplash.png

# (str) Icon of the application
icon.filename = %(source.dir)s/assets/icon.png

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (list) Permissions
android.permissions = INTERNET,ACCESS_NETWORK_STATE,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# (int) Target Android API, should be as high as possible.
android.api = 33

# (int) Minimum API your APK will support (21 covers Android 5.0+ including all Android Go versions)
android.minapi = 21


# (str) Android NDK version to use
android.ndk = 25b

# (str) Android SDK path to use
# android.sdk_path = 

# (str) Android NDK path to use
# android.ndk_path = 

# (bool) If True, then skip trying to update the Android sdk
android.skip_update = True

# (bool) If True, then automatically accept SDK license
android.accept_sdk_license = True

# (str) Android entry point
android.entrypoint = org.kivy.android.PythonActivity

# (list) List of architectures to build for
android.archs = arm64-v8a, armeabi-v7a

# (str) Directory for local custom build recipes
p4a.local_recipes = ./recipes

# (bool) Disallow Android system backup to protect sensitive session credentials
android.allow_backup = False

# (int) Log level (0 = error only, 1 = info, 2 = debug with command output)
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 0

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug with command output)
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 0
