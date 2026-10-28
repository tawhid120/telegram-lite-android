"""
Tests for Custom Important Contacts & Pinned Chats Storage.
Validates simultaneous multi-pinning (Contacts A, B, C), SQLite persistence, ordering, and renames.
"""

import os
import tempfile
import shutil
from storage.pin_store import PinStore


def test_simultaneous_pinning_contacts_a_b_c():
    """
    Test pinning contacts A, B, and C simultaneously as explicitly required.
    """
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp_dir, "test_pins.db")
        store = PinStore(db_path=db_path)

        # Contact A (ID: 1001)
        store.pin_chat(peer_id=1001, title="Contact A", username="contact_a", is_user=True)
        # Contact B (ID: 1002)
        store.pin_chat(peer_id=1002, title="Contact B", username="contact_b", is_user=True)
        # Contact C (ID: 1003)
        store.pin_chat(peer_id=1003, title="Contact C", username="contact_c", is_user=True)

        # Verify all three are pinned
        assert store.is_pinned(1001) is True
        assert store.is_pinned(1002) is True
        assert store.is_pinned(1003) is True
        assert store.is_pinned(9999) is False

        pinned_list = store.get_pinned_chats()
        assert len(pinned_list) == 3

        # Deterministic ordering: A, then B, then C
        ids = [c.peer_id for c in pinned_list]
        assert ids == [1001, 1002, 1003]

        # Persistence across reboots / new PinStore instance
        store_reloaded = PinStore(db_path=db_path)
        reloaded_pinned = store_reloaded.get_pinned_chats()
        assert len(reloaded_pinned) == 3
        assert [c.peer_id for c in reloaded_pinned] == [1001, 1002, 1003]

        # Profile rename without losing pin
        store.update_chat_metadata(peer_id=1001, title="Contact A (Renamed)", username="new_handle_a")
        updated_pinned = store.get_pinned_chats()
        assert store.is_pinned(1001) is True
        assert updated_pinned[0].title == "Contact A (Renamed)"
        assert updated_pinned[0].username == "new_handle_a"

        # Unpinning Contact B
        store.unpin_chat(1002)
        assert store.is_pinned(1002) is False
        assert len(store.get_pinned_chats()) == 2
        assert [c.peer_id for c in store.get_pinned_chats()] == [1001, 1003]

        # Toggle Pin
        # Contact C is currently pinned -> toggling unpins it
        res = store.toggle_pin(1003, "Contact C")
        assert res is False
        assert store.is_pinned(1003) is False

        # Toggling again pins it
        res = store.toggle_pin(1003, "Contact C")
        assert res is True
        assert store.is_pinned(1003) is True

    finally:
        shutil.rmtree(tmp_dir)


def test_reordering():
    tmp_dir = tempfile.mkdtemp()
    try:
        db_path = os.path.join(tmp_dir, "test_order.db")
        store = PinStore(db_path=db_path)

        store.pin_chat(1, "A")
        store.pin_chat(2, "B")
        store.pin_chat(3, "C")

        # Reverse the order
        store.reorder_pinned_chats([3, 2, 1])
        reordered = store.get_pinned_chats()
        assert [c.peer_id for c in reordered] == [3, 2, 1]
    finally:
        shutil.rmtree(tmp_dir)
