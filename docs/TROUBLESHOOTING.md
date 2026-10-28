# Troubleshooting and FAQ

## 1. Login & Verification Code Issues

### "I didn't receive an SMS code on my phone."
- **Why**: Telegram restricts SMS verification code delivery for third-party MTProto client applications.
- **Solution**: Open Telegram on your existing device (Desktop app, Telegram Web at `web.telegram.org`, or another smartphone). Telegram sends the login code directly into your active session as a chat message from the official "Telegram" service account (ID 777000). Enter that 5-digit code in Telegram Lite.

### "Too many requests / Rate limit in effect (FloodWait)"
- **Why**: Telegram server enforces a cooldown period if code requests or failed attempts occur too frequently.
- **Solution**: Wait the exact duration shown on screen (e.g. 60s, 300s). Do not attempt repeated logins while the timer is running.

### "Two-step verification password required"
- **Why**: Your Telegram account has cloud password protection enabled.
- **Solution**: Enter your 2FA password in the password field. You can use the eye icon (👁) to toggle visibility.

---

## 2. API Credentials Configuration

### "Invalid API ID or API Hash"
- **Why**: The numeric ID or 32-character hexadecimal hash entered does not match your developer profile.
- **Solution**:
  1. Visit [my.telegram.org](https://my.telegram.org) and log in.
  2. Navigate to **API development tools**.
  3. Copy your `App api_id` (e.g., `12345678`) and `App api_hash` (e.g., `abcdef0123456789...`).
  4. Enter them into the Telegram Lite setup screen or set `TG_API_ID` and `TG_API_HASH` in your environment.

---

## 3. Important Contacts & Pinning

### "Do my pinned contacts change my Telegram pins on other devices?"
- **No**. The custom pinning feature in Telegram Lite is completely local and stored on your device in SQLite. Telegram's native server pins have a strict limit of 5 chats; Telegram Lite allows you to pin as many contacts as you need (e.g. Contacts A, B, and C simultaneously) without affecting server state or notifying other contacts.

### "What happens if a pinned contact changes their name or username?"
- Telegram Lite stores the permanent numerical Telegram `peer_id` for custom pins. Even if the contact changes their display name or username, your custom pin and priority ordering remain intact.
