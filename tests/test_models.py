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
    from telegram_client.models import sanitize_text, ChatFolder

    # Bangla Unicode text with ZWJ and ZWNJ
    bangla_conjuncts = "বাংলা যুক্তবর্ণ: ক্\u200dষ, র\u200d্যা, ৎ এবং ক্\u200cল"
    assert "\u200d" in sanitize_text(bangla_conjuncts)
    assert "\u200c" in sanitize_text(bangla_conjuncts)
    assert sanitize_text(bangla_conjuncts) == bangla_conjuncts

    # Arabic script with bidi marks
    arabic_text = "مرحبا بالعالم! السلام عليكم ورحمة الله"
    assert sanitize_text(arabic_text) == arabic_text

    # Devanagari (Hindi)
    hindi_text = "नमस्ते दुनिया, आप कैसे हैं?"
    assert sanitize_text(hindi_text) == hindi_text

    # Complex emoji sequences (ZWJ family emoji and variation selector)
    emoji_family = "👨\u200d👩\u200d👧\u200d👦 ❤️\ufe0f 🚀"
    assert "\u200d" in sanitize_text(emoji_family)
    assert "\ufe0f" in sanitize_text(emoji_family)
    assert sanitize_text(emoji_family) == emoji_family

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

    # Unprintable control character stripping (C0/C1)
    corrupt_text = "Test\x00\x08String"
    assert sanitize_text(corrupt_text) == "TestString"


def test_chat_folder_model():
    from telegram_client.models import ChatFolder

    folder = ChatFolder(
        id=2,
        title="কাজের চ্যাট 💼",
        emoticon="💼",
        pinned_peer_ids=[101, 102],
        include_peer_ids=[103],
        exclude_peer_ids=[104],
        groups=True,
    )
    assert folder.id == 2
    assert folder.title == "কাজের চ্যাট 💼"
    assert folder.emoticon == "💼"
    assert folder.pinned_peer_ids == [101, 102]
    assert folder.groups is True


def test_message_item_media_fields():
    msg = MessageItem(
        id=77,
        chat_id=123,
        sender_id=456,
        sender_name="Alice",
        text="Check this photo",
        time_str="15:30",
        timestamp=1700000000.0,
        is_outgoing=False,
        media_type="photo",
        media_name="photo_123_77.jpg",
        media_size_str="1.2 MB",
        local_media_path="/path/to/downloads/photo_123_77.jpg",
    )
    assert msg.media_type == "photo"
    assert msg.media_size_str == "1.2 MB"
    assert msg.local_media_path == "/path/to/downloads/photo_123_77.jpg"
    assert msg.is_downloading is False
