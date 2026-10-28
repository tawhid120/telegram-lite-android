# Architecture Overview: Telegram Lite for Android Go

## 1. System Vision and Core Principles

Telegram Lite is a custom, lightweight Telegram client designed specifically for low-RAM (1GB - 2GB) Android Go devices. It connects directly to Telegram servers using the official MTProto protocol via Telethon, eliminating third-party middleman servers and safeguarding privacy.

### Key Architectural Pillars
- **Direct MTProto Connection**: Direct binary MTProto protocol connection with end-to-end server verification.
- **Single Connection Lifecycle**: Prevents duplicate connections and endless reconnect loops.
- **Zero UI-Thread Network Work**: The UI thread (Kivy) remains silky smooth; all asynchronous networking runs on a dedicated background `asyncio` event loop.
- **Data Decoupling**: Heavy MTProto raw entities and TL structures are never passed into UI widgets. Instead, clean, lightweight Python dataclasses (`ChatSummary`, `MessageItem`, `TelegramUser`) are projected and cached.
- **Offline-First & Instant Navigation**: In-memory tab filtering provides zero-latency switching between All, Personal, Groups, and Channels.

---

## 2. Component Architecture

```mermaid
flowchart TD
    UI[Kivy UI Layer\n(Screens & Components)]
    Bus[Thread-Safe Clock Callback Bridge]
    Wrapper[TelegramClientWrapper\n(Asyncio Background Worker)]
    MTProto[Telethon MTProto Client\n(Official Protocol)]
    
    subgraph Storage Layer
        SecStore[SecureSessionStore\n(Android Keystore / POSIX 0600)]
        PinDB[PinStore\n(Local SQLite Database)]
        Cache[CacheManager\n(LRU Bounded Memory & Disk)]
    end
    
    UI -->|User Actions| Wrapper
    Wrapper -->|Clock.schedule_once| Bus
    Bus -->|UI Updates| UI
    Wrapper <--> MTProto
    Wrapper <--> SecStore
    Wrapper <--> PinDB
    Wrapper <--> Cache
```

### Module Responsibilities

1. **`app/main.py`**:
   - Manages application startup, ScreenManager transitions (`NoTransition` for Android Go), and Android key events (Back button keycode 27).
   - Detects existing session credentials and routes directly to Chats or Login.

2. **`telegram_client/client_wrapper.py`**:
   - Maintains a single `TelegramClient` instance in a background daemon thread.
   - Schedules async coroutines thread-safely and posts results back to the Kivy UI thread via `Clock.schedule_once`.
   - Listens to real-time Telegram events (`events.NewMessage`) and dispatches updates.

3. **`telegram_client/auth_handler.py`**:
   - Manages MTProto authentication state transitions: `UNAUTHENTICATED`, `WAITING_CODE`, `WAITING_PASSWORD_2FA`, `AUTHENTICATED`.
   - Inspects `sent_code.type` to identify in-app service notifications (`SentCodeTypeApp`) vs SMS.
   - Handles Two-Step Verification (2FA cloud password) via `auth.checkPassword`.
   - Handles rate limits (`FloodWaitError`) with exact countdown timers.

4. **`storage/pin_store.py`**:
   - Manages custom pinned contacts in a local SQLite database (`pins.db`).
   - Completely decoupled from Telegram's native server-side pinned chats (which is capped at 5 and shared across devices).
   - Uses permanent 64-bit Telegram `peer_id`s rather than display names, ensuring pins survive contact renames.
   - Supports simultaneous pinning of multiple contacts (e.g. Contacts A, B, and C).

5. **`storage/secure_store.py`**:
   - Persists session strings and developer API credentials.
   - Uses Android private app storage (`/data/data/<package>/files/secure_store`) and POSIX `0600` permissions.
   - Implements safe credential wiping (zero-fill on logout).

6. **`storage/cache_manager.py`**:
   - Dual-tier cache: in-memory LRU cache + bounded disk cache.
   - Enforces strict disk and memory quotas with automatic eviction.
