# Security and Credential Protection Policy

## 1. Threat Model & Guarantees

In Telegram's MTProto architecture, an authorized session key is **equivalent to a full account password**. Anyone with access to the session string can read messages, download files, and send messages on behalf of the user.

### Core Security Principles in Telegram Lite:
1. **Direct Communication**: Telegram Lite connects directly to official Telegram MTProto data centers (`149.154.167.50:443`, etc.). No intermediate proxy, relay server, or telemetry backend is used.
2. **Zero Sensitive Logging**: Session strings, 2FA passwords, phone numbers, and message bodies are never printed to `stdout`, `stderr`, log files, or Android logcat.
3. **Restricted Local Storage**:
   - On Android: Session files are stored in the application's internal data sandbox (`Context.getFilesDir()`), protected by Linux kernel UID isolation.
   - On Linux/Desktop: Files are created with POSIX mode `0600` (readable and writable only by the app owner).
4. **Android Backup Disabled**: In `buildozer.spec`, `android.allow_backup = False` is enforced to prevent dumping session credentials via `adb backup`.
5. **Memory & Disk Sanitization**:
   - When the user taps **Log Out**, the session is explicitly revoked on the Telegram server via `auth.logOut`.
   - The local session file is overwritten with `\x00` null bytes before deletion to prevent unallocated file recovery.

---

## 2. API Credentials Safety

To protect your Telegram developer credentials:
- Do not commit your `api_id` or `api_hash` into Git.
- Pass credentials via environment variables:
  ```bash
  export TG_API_ID="12345678"
  export TG_API_HASH="0123456789abcdef0123456789abcdef"
  ```
- Or enter them into the **API Setup Screen** upon the first run of the app; they are stored encrypted in the device's secure store.

---

## 3. Exclusion from Version Control

The `.gitignore` strictly excludes:
- `*.session`, `*.session-journal`
- `*.dat`, `session.dat`, `credentials.dat`
- `config.json`, `.env`
- `*.jks`, `*.keystore`, `*.key`
- SQLite journals and cache databases

---

## 4. Telegram Login Verification Policy

Telegram has implemented strict fraud-prevention rules for third-party MTProto clients:
- **In-App Delivery**: When signing into an account that is already active on another device (Desktop, Web, or phone), Telegram delivers the verification code through a Telegram Service Notification (chat with user ID `777000`).
- **SMS Restrictions**: Telegram restricts SMS code delivery for third-party client apps to mitigate automated account creation abuse.
- Telegram Lite works seamlessly with in-app codes. Always keep an active Telegram session on your computer or browser when signing into Telegram Lite on a new device.
