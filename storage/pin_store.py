"""
Custom Important Contacts and Pinned Chats Storage.
Uses SQLite to persist custom pinned chats locally, completely independent of Telegram server state.
"""

import sqlite3
import os
import time
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger("PinStore")


@dataclass
class PinnedContact:
    peer_id: int
    title: str
    username: Optional[str] = None
    is_user: bool = True
    order_index: int = 0
    pinned_at: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "peer_id": self.peer_id,
            "title": self.title,
            "username": self.username,
            "is_user": self.is_user,
            "order_index": self.order_index,
            "pinned_at": self.pinned_at,
        }


class PinStore:
    """
    Manages local SQLite database for pinned contacts / important chats.
    Uses peer_id as primary key to prevent losing pins when users change their names or usernames.
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path:
            self._db_path = db_path
        else:
            base_dir = os.path.expanduser("~/.telegram_lite/data")
            os.makedirs(base_dir, exist_ok=True)
            self._db_path = os.path.join(base_dir, "pins.db")

        os.makedirs(os.path.dirname(os.path.abspath(self._db_path)), exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create the pinned_chats table if not exists."""
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pinned_chats (
                    peer_id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    username TEXT,
                    is_user INTEGER NOT NULL DEFAULT 1,
                    order_index INTEGER NOT NULL DEFAULT 0,
                    pinned_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_order 
                ON pinned_chats (order_index ASC, pinned_at DESC)
                """
            )
            conn.commit()

    def pin_chat(
        self,
        peer_id: int,
        title: str,
        username: Optional[str] = None,
        is_user: bool = True,
    ) -> bool:
        """
        Mark a conversation as custom-pinned.
        Deterministically orders it at the end of the pinned list.
        """
        try:
            now = time.time()
            with self._get_connection() as conn:
                # Find maximum order_index to place this new pin at the end
                cur = conn.execute("SELECT MAX(order_index) FROM pinned_chats")
                row = cur.fetchone()
                max_order = (row[0] if row[0] is not None else -1) + 1

                conn.execute(
                    """
                    INSERT INTO pinned_chats (peer_id, title, username, is_user, order_index, pinned_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(peer_id) DO UPDATE SET
                        title = excluded.title,
                        username = excluded.username,
                        is_user = excluded.is_user
                    """,
                    (peer_id, title, username, 1 if is_user else 0, max_order, now),
                )
                conn.commit()
            return True
        except Exception as e:
            logger.error("Error pinning chat %s: %s", peer_id, e)
            return False

    def unpin_chat(self, peer_id: int) -> bool:
        """Remove a conversation from custom pinned list."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM pinned_chats WHERE peer_id = ?", (peer_id,))
                conn.commit()
            return True
        except Exception as e:
            logger.error("Error unpinning chat %s: %s", peer_id, e)
            return False

    def toggle_pin(
        self,
        peer_id: int,
        title: str,
        username: Optional[str] = None,
        is_user: bool = True,
    ) -> bool:
        """Toggle pin state. Returns True if now pinned, False if unpinned."""
        if self.is_pinned(peer_id):
            self.unpin_chat(peer_id)
            return False
        else:
            self.pin_chat(peer_id, title, username, is_user)
            return True

    def is_pinned(self, peer_id: int) -> bool:
        """Check if peer_id is in custom pinned list."""
        try:
            with self._get_connection() as conn:
                cur = conn.execute(
                    "SELECT 1 FROM pinned_chats WHERE peer_id = ?", (peer_id,)
                )
                return cur.fetchone() is not None
        except Exception as e:
            logger.error("Error checking pin for %s: %s", peer_id, e)
            return False

    def get_pinned_peer_ids(self) -> set:
        """Fast lookup set of all pinned peer IDs."""
        try:
            with self._get_connection() as conn:
                cur = conn.execute("SELECT peer_id FROM pinned_chats")
                return {row[0] for row in cur.fetchall()}
        except Exception as e:
            logger.error("Error fetching pinned peer ids: %s", e)
            return set()

    def get_pinned_chats(self) -> List[PinnedContact]:
        """Return all pinned contacts in deterministic order."""
        try:
            with self._get_connection() as conn:
                cur = conn.execute(
                    """
                    SELECT peer_id, title, username, is_user, order_index, pinned_at
                    FROM pinned_chats
                    ORDER BY order_index ASC, pinned_at DESC
                    """
                )
                return [
                    PinnedContact(
                        peer_id=row["peer_id"],
                        title=row["title"],
                        username=row["username"],
                        is_user=bool(row["is_user"]),
                        order_index=row["order_index"],
                        pinned_at=row["pinned_at"],
                    )
                    for row in cur.fetchall()
                ]
        except Exception as e:
            logger.error("Error fetching pinned chats: %s", e)
            return []

    def update_chat_metadata(
        self, peer_id: int, title: str, username: Optional[str] = None
    ) -> None:
        """Update title or username if contact changes profile, retaining pin status."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    UPDATE pinned_chats
                    SET title = ?, username = ?
                    WHERE peer_id = ?
                    """,
                    (title, username, peer_id),
                )
                conn.commit()
        except Exception as e:
            logger.error("Error updating metadata for %s: %s", peer_id, e)

    def reorder_pinned_chats(self, peer_ids: List[int]) -> bool:
        """Update explicit ordering of pinned chats."""
        try:
            with self._get_connection() as conn:
                for idx, pid in enumerate(peer_ids):
                    conn.execute(
                        "UPDATE pinned_chats SET order_index = ? WHERE peer_id = ?",
                        (idx, pid),
                    )
                conn.commit()
            return True
        except Exception as e:
            logger.error("Error reordering pinned chats: %s", e)
            return False

    def clear_all_pins(self) -> bool:
        """Clear all custom pins."""
        try:
            with self._get_connection() as conn:
                conn.execute("DELETE FROM pinned_chats")
                conn.commit()
            return True
        except Exception as e:
            logger.error("Error clearing pins: %s", e)
            return False
