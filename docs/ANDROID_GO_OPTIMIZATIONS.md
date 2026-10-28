# Android Go Performance & Low-RAM Optimizations

Android Go Edition devices operate under strict physical hardware constraints:
- **RAM**: Typically 1 GB or 2 GB total system memory.
- **CPU**: Quad-core or entry-level octa-core (ARM Cortex-A53 / A7).
- **ZRAM / Swapping**: Active kernel compression; high memory pressure triggers aggressive low-memory killer (LMK) eviction.

Telegram Lite incorporates specific architectural design choices to run smoothly within these limits:

---

## 1. Zero-Copy Dataclass Mapping

Official Telegram applications keep extensive object trees in memory for every dialog, message, user, channel, and sticker pack. In a Python environment, MTProto TL structures can rapidly consume 50-100 MB of RAM.

In Telegram Lite:
- The MTProto worker processes raw TL objects and extracts only the minimal required scalar values into lightweight Python dataclasses:
  - `ChatSummary`: Title, peer ID, 1-line snippet, unread count, timestamp.
  - `MessageItem`: ID, sender name, text, time string.
- Raw MTProto objects are promptly garbage collected.

---

## 2. Bounded Dual-Tier Cache & LRU Eviction

Avatars and downloaded media are strictly throttled:
- **In-Memory Cache**: Fixed capacity using an `OrderedDict` LRU structure (40 items in normal mode, 15 items in Low-Resource Mode).
- **Disk Cache**: Capped at 25 MB (10 MB in Low-Resource Mode). When the ceiling is reached, the oldest accessed files are pruned automatically.
- **On-Demand Loading**: Media files and message history are loaded only when explicitly opened or scrolled. Historical media is never pre-downloaded.

---

## 3. Screen Transitions & Rendering Efficiency

- **`NoTransition` Default**: Animated sliding transitions require GPU framebuffer copies of both incoming and outgoing screens. Using `NoTransition` instantly swaps views with zero additional frame allocation.
- **Vector-Free Simple Canvas Primitives**: All UI bubbles and avatars use simple OpenGL ES rounded rectangles and ellipses without complex shaders, gradients, or blur passes.

---

## 4. Single-Threaded Network Worker

- Rather than spawning arbitrary threads per request, Telegram Lite uses a **single dedicated background worker thread** running Python's `asyncio` event loop.
- All requests are serialized onto the loop, preventing race conditions and thread-stack RAM overhead.
