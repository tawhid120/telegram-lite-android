"""
Tests for lightweight Telegram models.
"""

from telegram_client.models import ChatSummary, MessageItem, ChatType, TelegramUser, CodeDeliveryType, AuthState


def test_chat_summary_initials():
    # Two words
    c1 = ChatSummary(peer_id=101, title="Alice Smith", chat_type=ChatType.PERSONAL)
    assert c1.initials == "AS"

    # Single word
    c2 = ChatSummary(peer_id=102, title="Bob", chat_type=ChatType.PERSONAL)
    assert c2.initials == "BO"

    # Empty title
    c3 = ChatSummary(peer_id=103, title="", chat_type=ChatType.GROUP)
    assert c3.initials == "?"


def test_chat_summary_preview_truncation():
    long_msg = "Hello! " * 30
    summary = ChatSummary(
        peer_id=200,
        title="Channel",
        chat_type=ChatType.CHANNEL,
        last_message_text=long_msg,
    )
    assert len(summary.display_preview) <= 60
    assert summary.display_preview.endswith("...")


def test_telegram_user():
    u = TelegramUser(id=999, first_name="Tawhid", last_name="Islam", username="tawhid")
    assert u.full_name == "Tawhid Islam"
    assert u.username == "tawhid"

    u_single = TelegramUser(id=1000, first_name="Admin")
    assert u_single.full_name == "Admin"


def test_message_item():
    m = MessageItem(
        id=1,
        chat_id=123,
        sender_id=456,
        sender_name="John",
        text="Testing message",
        time_str="12:30",
        timestamp=1600000000.0,
        is_outgoing=True,
    )
    assert m.formatted_time == "12:30"
    assert m.is_outgoing is True


def test_unicode_bangla_and_emoji_sanitization():
    from telegram_client.models import sanitize_text

    # Bangla Unicode text
    bangla_text = "কেমন আছেন? এটি একটি টেলিগ্রাম মেসেজ।"
    assert sanitize_text(bangla_text) == bangla_text

    # Model integration with Bangla
    summary = ChatSummary(
        peer_id=500,
        title="তাহমিদ হাসান",
        chat_type=ChatType.PERSONAL,
        last_message_text="হ্যালো ভাই, কি খবর?",
    )
    assert summary.title == "তাহমিদ হাসান"
    assert summary.last_message_text == "হ্যালো ভাই, কি খবর?"
    assert len(summary.initials) > 0

    # Unprintable control character stripping
    corrupt_text = "Test\x00\x08String"
    assert sanitize_text(corrupt_text) == "TestString"
