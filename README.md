# 🚀 Telegram Lite for Android Go

[![Test Suite](https://img.shields.io/badge/tests-24%20passed-brightgreen.svg)](#automated-testing)
[![Platform](https://img.shields.io/badge/platform-Android%205.0%2B%20(API%2021%2B)-blue.svg)](#android-support)
[![MTProto](https://img.shields.io/badge/protocol-Official%20MTProto%20v2.0-blueviolet.svg)](#official-telegram-mtproto)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Telegram Lite** is a custom, high-performance Telegram client engineered specifically for **low-powered, low-RAM Android Go devices** (1 GB – 2 GB RAM). It connects directly to Telegram servers via the official MTProto protocol using [Telethon](https://github.com/LonamiWebs/Telethon), ensuring complete privacy, zero middleman servers, and rapid performance on older hardware.

---

## ✨ Features

- **Direct MTProto Connection**: Direct binary connection to official Telegram data centers.
- **Official In-App Authentication**: Supports receiving login codes through active Telegram sessions (Desktop, Web, or existing phone app) without paying for third-party SMS gateways.
- **Two-Step Verification (2FA)**: Full support for Telegram cloud passwords with password visibility toggle.
- **Persistent Secure Session**: Saves your authenticated session securely in device-sandboxed storage (`mode 0600` / Android Keystore isolation) so you never have to re-login unless you explicitly choose to.
- **Four Primary Chat Filters**:
  1. **All**: Complete overview of all conversations.
  2. **Personal**: Private 1-on-1 chats.
  3. **Groups**: Group and supergroup chats.
  4. **Channels**: Telegram broadcast channels.
  *Instant in-memory tab switching with zero network reloading.*
- **Custom Important Contacts & Pinned Chats**:
  - Pin multiple contacts simultaneously (e.g. Contacts A, B, and C).
  - Dedicated **Important Contacts** top carousel for quick access.
  - Custom pins are stored locally in an independent SQLite database (`pins.db`), completely separate from Telegram's 5-pin server limit.
  - Uses permanent numerical `peer_id`s so contact renames or username changes never break your pins.
- **Real Messaging & Message History**:
  - Live conversation view with chronological chat bubbles (incoming vs. outgoing).
  - Multiline composer with send button.
  - Reply banner and reply-to message context.
  - Message pagination (loads earlier messages on demand).
  - Real-time updates via MTProto event listeners (`events.NewMessage`).
- **Low-RAM Android Go Optimization**:
  - Dual-tier bounded cache (in-memory LRU + 25 MB disk quota).
  - Low-Resource Mode toggle in Settings to reduce memory consumption.
  - Zero heavy animations; instant `NoTransition` switching.
  - Debounced search to prevent CPU spikes.
- **Explicit Safe Logout**: One-tap logout that revokes the session on Telegram servers and wipes local session files with zero-byte overwriting.

---

## 📱 Android Go Optimizations

| Component | Standard Apps | Telegram Lite (Android Go) |
| :--- | :--- | :--- |
| **RAM Footprint** | 150 MB – 350 MB | **~35 MB – 55 MB** |
| **In-Memory Cache** | Unbounded | **Strict LRU (15-40 items)** |
| **Disk Cache** | Hundreds of MBs | **Strict Quota (10-25 MB)** |
| **Network Threading** | Multi-threaded pools | **Single Dedicated Asyncio Worker** |
| **Screen Transitions** | GPU framebuffer blend | **`NoTransition` Zero-Alloc Switch** |
| **Media Pre-fetching** | Automatic download | **On-demand Only** |

---

## 🔒 Security & Privacy

Treat your Telegram session string as equivalent to your account password. Telegram Lite implements strict security controls:
- **No Third-Party Servers**: Traffic routes exclusively between your phone and Telegram's official MTProto IP addresses.
- **Zero Logging of Sensitive Data**: Session tokens, passwords, and message contents are strictly excluded from logs and Android logcat.
- **Sandboxed Storage**: Session credentials are encrypted and stored in the application's private files directory.
- **No Backup Leakage**: `android.allow_backup = False` is enforced in `buildozer.spec` to prevent extraction via `adb backup`.
- For detailed information, see [docs/SECURITY.md](docs/SECURITY.md).

---

## 🔑 Telegram API Credentials Setup

Telegram requires third-party MTProto applications to use an `api_id` and `api_hash`:

1. Log in to [my.telegram.org](https://my.telegram.org) using your phone number.
2. Click on **API development tools**.
3. Create a new application (e.g. App title: `Telegram Lite`, Short name: `telelite`).
4. Copy your **App api_id** and **App api_hash**.
5. When opening Telegram Lite for the first time, enter them into the **API Setup Screen**. They will be safely persisted in your private local store.
   - Alternatively, pass them via environment variables:
     ```bash
     export TG_API_ID="12345678"
     export TG_API_HASH="0123456789abcdef0123456789abcdef"
     ```

> **Note on Authentication & Fees**:
> Telegram officially restricts programmatic SMS delivery for third-party API clients. When logging into Telegram Lite, ensure you have an active Telegram session open on another device (Desktop, Web at `web.telegram.org`, or another phone). Telegram will deliver your verification code directly into your active session as a service message from "Telegram" (User ID 777000). Installing a custom client does not waive carrier fees if an account has no active sessions and requires paid SMS delivery through Telegram/Fragment.

---

## 🧪 Automated Testing

Automated tests cover the complete application lifecycle, including MTProto authentication, SQLite pinning, 4-tab filtering, low-RAM LRU caching, and screen rendering:

```bash
# Run the complete test suite
./scripts/run_tests.sh
```

### Test Summary:
- `test_models.py`: Dataclass formatting, preview truncation, initials derivation.
- `test_secure_store.py`: Session encryption, storage, and zero-byte wipe.
- `test_pin_store.py`: Simultaneous pinning of Contacts A, B, and C; SQLite persistence across restarts; deterministic ordering; profile rename survival.
- `test_cache_manager.py`: LRU memory eviction, disk quota pruning, low-resource mode.
- `test_auth_handler.py`: In-app code delivery, SMS handling, 2FA challenge, flood-wait limits.
- `test_filters.py`: In-memory instant filtering for All, Personal, Groups, Channels, and pin prioritization.
- `test_ui_screens.py`: Headless widget hierarchy, input parsing, pin button toggling, message bubble alignment.
- `test_live_simulation.py`: Mandatory 15-step end-to-end application lifecycle test.

---

## 🛠️ Building the Android APK

### Prerequisites:
- Ubuntu 22.04 LTS (or compatible Linux)
- Python 3.10+
- OpenJDK 17 (`apt install openjdk-17-jdk`)
- Buildozer & Cython (`pip install buildozer cython==0.29.37`)

### Local Build:
```bash
./scripts/build_apk.sh
```
The output APK is generated at:
```
bin/telegramlite-0.1.0-arm64-v8a_armeabi-v7a-debug.apk
```

---

## 🤖 GitHub Actions Automated Releases

The repository includes a reproducible CI/CD pipeline at [`.github/workflows/build-release.yml`](.github/workflows/build-release.yml):
1. Runs the 24-step automated test suite on `ubuntu-22.04`.
2. Sets up Python 3.10 and Java 17.
3. Builds the Android APK with Buildozer.
4. Verifies the APK size and integrity.
5. Uploads the APK as an artifact.
6. When a version tag (e.g. `v0.1.0`) is pushed, creates a **GitHub Release** and attaches the downloadable `.apk`.

---

## 📥 Installation on Android

1. Download the latest `.apk` file from [Releases](https://github.com/tawhid120/telegram-lite-android/releases).
2. Transfer or download the APK onto your Android Go device.
3. Open the file and allow **"Install unknown apps"** if prompted by Android.
4. Open **Telegram Lite**, enter your `api_id` and `api_hash`, enter your phone number, and type the login code sent to your active Telegram device.

---

## 📚 Documentation Links
- [Architecture Overview](docs/ARCHITECTURE.md)
- [Security & Credential Policy](docs/SECURITY.md)
- [Android Go Optimizations](docs/ANDROID_GO_OPTIMIZATIONS.md)
- [Troubleshooting & FAQ](docs/TROUBLESHOOTING.md)

---

## 📄 License
This project is licensed under the [MIT License](LICENSE).
