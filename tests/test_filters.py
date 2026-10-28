"""
Tests for Four Tab Filters (All, Personal, Groups, Channels) and Custom Pin Prioritization.
"""

from telegram_client.models import ChatSummary, ChatType
from telegram_client.client_wrapper import TelegramClientWrapper
from unittest.mock import MagicMock


def test_four_tab_filtering_and_pin_prioritization():
    # Setup mock dependencies
    secure_store = MagicMock()
    pin_store = MagicMock()
    cache_manager = MagicMock()

    wrapper = TelegramClientWrapper(
        api_id=123,
        api_hash="abc",
        secure_store=secure_store,
        pin_store=pin_store,
        cache_manager=cache_manager,
    )

    # Populate cached summaries
    c_personal_1 = ChatSummary(peer_id=1, title="Contact A", chat_type=ChatType.PERSONAL, is_pinned_locally=True)
    c_personal_2 = ChatSummary(peer_id=2, title="Contact B", chat_type=ChatType.PERSONAL, is_pinned_locally=False)
    c_group_1 = ChatSummary(peer_id=3, title="Developers Group", chat_type=ChatType.GROUP, is_pinned_locally=False)
    c_group_2 = ChatSummary(peer_id=4, title="Project Team", chat_type=ChatType.GROUP, is_pinned_locally=True)
    c_channel_1 = ChatSummary(peer_id=5, title="News Channel", chat_type=ChatType.CHANNEL, is_pinned_locally=False)

    wrapper._cached_summaries = [c_personal_1, c_personal_2, c_group_1, c_group_2, c_channel_1]

    # Test ALL filter: All 5, pinned first
    all_res = wrapper.filter_cached_conversations(ChatType.ALL)
    assert len(all_res) == 5
    # Pinned items (1 and 4) must appear first
    assert all_res[0].peer_id in (1, 4)
    assert all_res[1].peer_id in (1, 4)

    # Test PERSONAL filter: Only personal chats (1 and 2)
    personal_res = wrapper.filter_cached_conversations(ChatType.PERSONAL)
    assert len(personal_res) == 2
    assert [c.peer_id for c in personal_res] == [1, 2]
    assert personal_res[0].is_pinned_locally is True

    # Test GROUP filter: Only groups (3 and 4)
    group_res = wrapper.filter_cached_conversations(ChatType.GROUP)
    assert len(group_res) == 2
    # Pinned group (4) must be first
    assert group_res[0].peer_id == 4
    assert group_res[1].peer_id == 3

    # Test CHANNEL filter: Only channels (5)
    channel_res = wrapper.filter_cached_conversations(ChatType.CHANNEL)
    assert len(channel_res) == 1
    assert channel_res[0].peer_id == 5
