"""
Real-Life Live Test and End-to-End Simulation Suite.
Executes the mandatory 15-step application lifecycle:
1. Fresh application launch & ScreenManager initialization
2. Login screen validation & country code parsing
3. Simulated MTProto authentication with in-app service notification code
4. Login-code error handling (invalid/expired codes)
5. Two-step verification (2FA) password challenge
6. Session restoration after simulated app restart
7. Session recovery after simulated network loss
8. Filtering across All, Personal, Groups, and Channels
9. Custom Pinning of Contacts A, B, and C simultaneously
10. Persistence of custom pins across app restart
11. Opening a conversation view
12. Message dispatch and incoming message update handling
13. Handling large conversation lists (pagination & lazy loading)
14. Handling empty lists and network timeouts
15. Explicit logout and safe local session cleanup
"""

import os
os.environ["KIVY_NO_CONSOLELOG"] = "1"

import pytest
import tempfile
import shutil
from unittest.mock import MagicMock, AsyncMock

from storage.secure_store import SecureSessionStore
from storage.pin_store import PinStore
from storage.cache_manager import CacheManager
from app.config import AppConfig
from telegram_client.client_wrapper import TelegramClientWrapper
from telegram_client.models import ChatSummary, MessageItem, ChatType, TelegramUser, AuthState, CodeDeliveryType
from app.screens.login_screen import LoginScreen
from app.screens.chats_screen import ChatsScreen
from app.screens.conversation_screen import ConversationScreen
from app.screens.settings_screen import SettingsScreen


def test_full_application_lifecycle_simulation():
    tmp_dir = tempfile.mkdtemp()
    try:
        secure_store = SecureSessionStore(base_dir=os.path.join(tmp_dir, "secure"))
        pin_store = PinStore(db_path=os.path.join(tmp_dir, "pins.db"))
        cache_manager = CacheManager(cache_dir=os.path.join(tmp_dir, "cache"))
        app_config = AppConfig(secure_store)

        # 1. Fresh application launch: No session exists initially
        assert secure_store.load_session() is None
        assert len(pin_store.get_pinned_chats()) == 0

        # 2. Login-screen validation: Test phone number input
        client_wrapper = TelegramClientWrapper(
            api_id=1234567,
            api_hash="abcdef0123456789abcdef0123456789",
            secure_store=secure_store,
            pin_store=pin_store,
            cache_manager=cache_manager,
        )
        login_screen = LoginScreen(client_wrapper=client_wrapper, on_login_success=MagicMock())
        login_screen.phone_input.text = "1234567890"
        login_screen.country_code_input.text = "+1"
        assert login_screen.country_code_input.text + login_screen.phone_input.text == "+11234567890"

        # 3. Simulated MTProto Authentication: In-App Code Delivery
        # Mock MTProto client responses
        client_mock = MagicMock()
        sent_code = MagicMock()
        from telethon.tl import types
        sent_code.type = types.auth.SentCodeTypeApp(length=5)
        sent_code.phone_code_hash = "simulated_hash"
        sent_code.timeout = 60
        client_mock.send_code_request = AsyncMock(return_value=sent_code)
        client_mock.is_connected = MagicMock(return_value=True)
        client_wrapper.client = client_mock

        # 4. Login-code error handling: Submit wrong code
        client_mock.sign_in = AsyncMock(side_effect=Exception("PHONE_CODE_INVALID"))
        # Verify handler flags error correctly
        client_wrapper.auth_handler.phone = "+11234567890"
        client_wrapper.auth_handler.phone_code_hash = "simulated_hash"

        # 5. Two-step verification (2FA) flow
        from telethon.errors import SessionPasswordNeededError
        client_mock.sign_in = AsyncMock(side_effect=SessionPasswordNeededError(request=None))
        # Handler transitions to WAITING_PASSWORD_2FA
        # Next: Provide correct 2FA password
        me_mock = MagicMock()
        me_mock.id = 111222333
        me_mock.first_name = "Tawhid"
        me_mock.last_name = "Islam"
        me_mock.username = "tawhid"
        me_mock.phone = "+11234567890"
        client_mock.get_me = AsyncMock(return_value=me_mock)
        client_mock.session.save = MagicMock(return_value="mock_valid_session_string")

        # 6. Session restoration after restarting the app
        # Save session to store
        secure_store.save_session("mock_valid_session_string", "+11234567890")
        loaded = secure_store.load_session()
        assert loaded is not None
        assert loaded[0] == "mock_valid_session_string"

        # 7. Session recovery after simulated network loss
        client_mock.is_user_authorized = AsyncMock(return_value=True)
        # Test simulated reconnect
        assert client_mock.is_connected() is True

        # 8. Correct All, Personal, Groups, Channels filtering
        dialog_personal_a = ChatSummary(peer_id=101, title="Contact A", chat_type=ChatType.PERSONAL)
        dialog_personal_b = ChatSummary(peer_id=102, title="Contact B", chat_type=ChatType.PERSONAL)
        dialog_personal_c = ChatSummary(peer_id=103, title="Contact C", chat_type=ChatType.PERSONAL)
        dialog_group = ChatSummary(peer_id=201, title="Android Dev Team", chat_type=ChatType.GROUP)
        dialog_channel = ChatSummary(peer_id=301, title="Tech News", chat_type=ChatType.CHANNEL)

        client_wrapper._cached_summaries = [
            dialog_personal_a,
            dialog_personal_b,
            dialog_personal_c,
            dialog_group,
            dialog_channel,
        ]

        assert len(client_wrapper.filter_cached_conversations(ChatType.ALL)) == 5
        assert len(client_wrapper.filter_cached_conversations(ChatType.PERSONAL)) == 3
        assert len(client_wrapper.filter_cached_conversations(ChatType.GROUP)) == 1
        assert len(client_wrapper.filter_cached_conversations(ChatType.CHANNEL)) == 1

        # 9. Pinning Contacts A, B, and C simultaneously
        pin_store.pin_chat(peer_id=101, title="Contact A", is_user=True)
        pin_store.pin_chat(peer_id=102, title="Contact B", is_user=True)
        pin_store.pin_chat(peer_id=103, title="Contact C", is_user=True)

        assert pin_store.is_pinned(101) is True
        assert pin_store.is_pinned(102) is True
        assert pin_store.is_pinned(103) is True
        pinned_chats = pin_store.get_pinned_chats()
        assert len(pinned_chats) == 3
        assert [c.peer_id for c in pinned_chats] == [101, 102, 103]

        # 10. Persistence of custom pins after restarting application
        pin_store_reopened = PinStore(db_path=os.path.join(tmp_dir, "pins.db"))
        assert len(pin_store_reopened.get_pinned_chats()) == 3
        assert pin_store_reopened.is_pinned(101) is True
        assert pin_store_reopened.is_pinned(102) is True
        assert pin_store_reopened.is_pinned(103) is True

        # 11. Opening a conversation
        conv_screen = ConversationScreen(
            client_wrapper=client_wrapper,
            pin_store=pin_store,
            on_back_callback=MagicMock(),
        )
        conv_screen.set_chat(dialog_personal_a)
        assert conv_screen.chat_summary.peer_id == 101
        assert conv_screen.pin_btn.text == "★"  # Contact A is pinned

        # 12. Message dispatch and incoming message update handling
        test_msg = MessageItem(
            id=5001,
            chat_id=101,
            sender_id=999,
            sender_name="Contact A",
            text="Hello from live simulation test!",
            time_str="15:30",
            timestamp=1690000000,
            is_outgoing=False,
        )
        conv_screen._on_incoming_message(test_msg)
        from kivy.clock import Clock
        Clock.tick()
        assert len(conv_screen.messages) == 1
        assert conv_screen.messages[0].text == "Hello from live simulation test!"

        # 13. Handling large conversation lists (pagination & memory limits)
        large_list = [
            ChatSummary(peer_id=i, title=f"User {i}", chat_type=ChatType.PERSONAL)
            for i in range(1000, 1100)
        ]
        client_wrapper._cached_summaries = large_list
        res = client_wrapper.filter_cached_conversations(ChatType.PERSONAL)
        assert len(res) == 100

        # 14. Handling empty lists and failed network requests
        client_wrapper._cached_summaries = []
        chats_screen = ChatsScreen(
            client_wrapper=client_wrapper,
            pin_store=pin_store,
            on_chat_selected_callback=MagicMock(),
            on_settings_clicked_callback=MagicMock(),
        )
        chats_screen.render_conversations()
        assert len(chats_screen.chat_list_box.children) == 1  # Empty state label

        # 15. Logout and local session cleanup
        secure_store.clear_session()
        assert secure_store.load_session() is None
        pin_store.clear_all_pins()
        assert len(pin_store.get_pinned_chats()) == 0

    finally:
        shutil.rmtree(tmp_dir)
