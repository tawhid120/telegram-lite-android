"""
UI Components and Screen Unit Tests for Telegram Lite.
Executes in headless/mock window environment to verify widget building, layout, and event handlers.
"""

import os
os.environ["KIVY_NO_CONSOLELOG"] = "1"

import pytest
from unittest.mock import MagicMock

from app.config import AppConfig
from app.screens.api_setup_screen import ApiSetupScreen
from app.screens.login_screen import LoginScreen
from app.screens.chats_screen import ChatsScreen
from app.screens.conversation_screen import ConversationScreen
from app.screens.settings_screen import SettingsScreen
from app.components.chat_item import ChatItemWidget
from app.components.pinned_section import PinnedSectionWidget, PinnedContact
from app.components.message_bubble import MessageBubbleWidget
from telegram_client.models import ChatSummary, ChatType, MessageItem


def test_api_setup_screen():
    store = MagicMock()
    app_config = AppConfig(store)
    cb = MagicMock()
    screen = ApiSetupScreen(app_config=app_config, on_configured_callback=cb)
    assert screen.name == ""

    # Enter invalid values
    screen.api_id_input.text = "abc"
    screen.api_hash_input.text = "123"
    screen._on_save_clicked(None)
    assert "valid number" in screen.error_label.text

    # Enter valid values
    screen.api_id_input.text = "1234567"
    screen.api_hash_input.text = "abcdef0123456789abcdef0123456789"
    screen._on_save_clicked(None)
    cb.assert_called_once_with(1234567, "abcdef0123456789abcdef0123456789")


def test_login_screen_state_rendering():
    client = MagicMock()
    cb = MagicMock()
    login_screen = LoginScreen(client_wrapper=client, on_login_success=cb)
    assert login_screen.current_step == "phone"

    # Test transitioning to 2FA screen
    login_screen._render_2fa_step()
    assert login_screen.current_step == "password"
    assert login_screen.pwd_input.password is True

    # Test toggling password visibility
    login_screen._toggle_password_visibility(None)
    assert login_screen.pwd_input.password is False


def test_chat_item_widget():
    summary = ChatSummary(
        peer_id=123,
        title="Alice",
        chat_type=ChatType.PERSONAL,
        last_message_text="Hello world",
        unread_count=3,
        is_pinned_locally=True,
    )
    click_cb = MagicMock()
    pin_cb = MagicMock()
    item = ChatItemWidget(summary, click_cb, pin_cb)
    assert item.title_label.text == "Alice"
    assert item.pin_btn.text == "★"
    assert item.badge_label.text == "3"

    # Simulate pin button click
    item._on_pin_clicked(None)
    pin_cb.assert_called_once_with(summary)


def test_pinned_section_widget():
    cb = MagicMock()
    pinned_widget = PinnedSectionWidget(on_contact_selected=cb)

    contacts = [
        PinnedContact(peer_id=1, title="Contact A"),
        PinnedContact(peer_id=2, title="Contact B"),
        PinnedContact(peer_id=3, title="Contact C"),
    ]
    pinned_widget.update_pinned_contacts(contacts)
    # Should contain 3 badge widgets
    assert len(pinned_widget.contacts_container.children) == 3
    assert pinned_widget.opacity == 1

    # Empty contacts hides section
    pinned_widget.update_pinned_contacts([])
    assert pinned_widget.opacity == 0


def test_message_bubble_widget():
    msg_out = MessageItem(
        id=1,
        chat_id=10,
        sender_id=100,
        sender_name="Me",
        text="Outgoing text",
        time_str="14:00",
        timestamp=1000,
        is_outgoing=True,
    )
    bubble_out = MessageBubbleWidget(msg_out)
    assert bubble_out.message.is_outgoing is True

    msg_in = MessageItem(
        id=2,
        chat_id=10,
        sender_id=200,
        sender_name="Partner",
        text="Incoming reply",
        time_str="14:01",
        timestamp=1001,
        is_outgoing=False,
        reply_to_msg_id=1,
        reply_to_text="Outgoing text",
    )
    bubble_in = MessageBubbleWidget(msg_in, is_group=True)
    assert bubble_in.message.is_outgoing is False


def test_message_bubble_media_and_actions():
    media_cb = MagicMock()
    msg_media = MessageItem(
        id=3,
        chat_id=10,
        sender_id=300,
        sender_name="Alice",
        text="Photo caption",
        time_str="14:05",
        timestamp=1002,
        is_outgoing=False,
        media_type="photo",
        media_name="photo_10_3.jpg",
        media_size_str="2.5 MB",
    )
    bubble = MessageBubbleWidget(msg_media, on_media_action_callback=media_cb)
    assert bubble.message.media_type == "photo"

    # Simulate download action
    bubble._on_media_clicked("download")
    media_cb.assert_called_once_with(msg_media, "download")


def test_chats_screen_dynamic_folders():
    from telegram_client.models import ChatFolder

    client = MagicMock()
    folder1 = ChatFolder(id=1, title="Personal VIP", emoticon="⭐️")
    folder2 = ChatFolder(id=2, title="Crypto News", emoticon="📈")
    client._cached_folders = [folder1, folder2]
    client._cached_summaries = []

    pin_store = MagicMock()
    pin_store.get_pinned_chats.return_value = []

    screen = ChatsScreen(
        client_wrapper=client,
        pin_store=pin_store,
        on_chat_selected_callback=MagicMock(),
        on_settings_clicked_callback=MagicMock(),
    )

    # Rebuild tabs with the mock folders
    screen._rebuild_folder_tabs()
    # Check that dynamic folder tabs exist: All + folder1 + folder2 = 3 buttons
    assert len(screen.folder_tab_buttons) == 3
    assert None in screen.folder_tab_buttons
    assert 1 in screen.folder_tab_buttons
    assert 2 in screen.folder_tab_buttons

    # Select folder 1
    screen.select_folder(folder1)
    assert screen.current_folder == folder1
    client.filter_conversations_by_folder.assert_called_with(folder1)
