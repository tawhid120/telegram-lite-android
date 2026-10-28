"""
Tests for MTProto AuthHandler.
Mocks Telethon client to verify in-app code delivery, 2FA password flow, and error states.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from telethon.tl import types
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    FloodWaitError,
    PasswordHashInvalidError,
)

from storage.secure_store import SecureSessionStore
from telegram_client.auth_handler import AuthHandler
from telegram_client.models import AuthState, CodeDeliveryType


@pytest.mark.asyncio
async def test_auth_send_code_in_app():
    store = MagicMock(spec=SecureSessionStore)
    handler = AuthHandler(store)

    client = MagicMock()
    # Mock Telegram sentCode response with SentCodeTypeApp (in-app code)
    sent_code = MagicMock()
    sent_code.type = types.auth.SentCodeTypeApp(length=5)
    sent_code.phone_code_hash = "hash_12345"
    sent_code.timeout = 60
    client.send_code_request = AsyncMock(return_value=sent_code)

    success, msg, delivery, timeout = await handler.send_code(client, "+1234567890")
    assert success is True
    assert delivery == CodeDeliveryType.APP_IN_APP
    assert handler.state == AuthState.WAITING_CODE
    assert "Telegram session" in msg
    assert handler.phone_code_hash == "hash_12345"


@pytest.mark.asyncio
async def test_auth_send_code_invalid_phone():
    store = MagicMock(spec=SecureSessionStore)
    handler = AuthHandler(store)

    client = MagicMock()
    client.send_code_request = AsyncMock(side_effect=PhoneNumberInvalidError(request=None))

    success, msg, delivery, timeout = await handler.send_code(client, "invalid")
    assert success is False
    assert handler.state == AuthState.ERROR
    assert "Invalid phone number" in msg


@pytest.mark.asyncio
async def test_auth_send_code_flood_wait():
    store = MagicMock(spec=SecureSessionStore)
    handler = AuthHandler(store)

    client = MagicMock()
    client.send_code_request = AsyncMock(side_effect=FloodWaitError(request=None, capture=120))

    success, msg, delivery, timeout = await handler.send_code(client, "+1234567890")
    assert success is False
    assert handler.state == AuthState.ERROR
    assert "120s" in msg
    assert timeout == 120


@pytest.mark.asyncio
async def test_auth_sign_in_success():
    store = MagicMock(spec=SecureSessionStore)
    handler = AuthHandler(store)
    handler.phone = "+1234567890"
    handler.phone_code_hash = "hash_12345"
    handler.state = AuthState.WAITING_CODE

    client = MagicMock()
    client.sign_in = AsyncMock()
    me = MagicMock()
    me.id = 777
    me.first_name = "Tawhid"
    me.last_name = None
    me.username = "tawhid"
    me.phone = "+1234567890"
    client.get_me = AsyncMock(return_value=me)
    client.session.save = MagicMock(return_value="saved_session_string")

    success, msg, state = await handler.sign_in_with_code(client, "12345")
    assert success is True
    assert state == AuthState.AUTHENTICATED
    assert handler.current_user is not None
    assert handler.current_user.id == 777
    store.save_session.assert_called_once_with("saved_session_string", "+1234567890")


@pytest.mark.asyncio
async def test_auth_sign_in_requires_2fa():
    store = MagicMock(spec=SecureSessionStore)
    handler = AuthHandler(store)
    handler.phone = "+1234567890"
    handler.phone_code_hash = "hash_12345"
    handler.state = AuthState.WAITING_CODE

    client = MagicMock()
    client.sign_in = AsyncMock(side_effect=SessionPasswordNeededError(request=None))

    success, msg, state = await handler.sign_in_with_code(client, "12345")
    assert success is True
    assert state == AuthState.WAITING_PASSWORD_2FA
    assert handler.state == AuthState.WAITING_PASSWORD_2FA

    # Now verify entering 2FA password
    client.sign_in = AsyncMock()
    me = MagicMock()
    me.id = 777
    me.first_name = "Tawhid"
    me.last_name = None
    me.username = "tawhid"
    me.phone = "+1234567890"
    client.get_me = AsyncMock(return_value=me)
    client.session.save = MagicMock(return_value="2fa_session_str")

    pwd_success, pwd_msg, pwd_state = await handler.sign_in_with_password(client, "my_2fa_pass")
    assert pwd_success is True
    assert pwd_state == AuthState.AUTHENTICATED
    assert handler.state == AuthState.AUTHENTICATED
    store.save_session.assert_called_with("2fa_session_str", "+1234567890")


@pytest.mark.asyncio
async def test_auth_sign_in_invalid_code():
    store = MagicMock(spec=SecureSessionStore)
    handler = AuthHandler(store)
    handler.phone = "+1234567890"
    handler.phone_code_hash = "hash_12345"
    handler.state = AuthState.WAITING_CODE

    client = MagicMock()
    client.sign_in = AsyncMock(side_effect=PhoneCodeInvalidError(request=None))

    success, msg, state = await handler.sign_in_with_code(client, "99999")
    assert success is False
    assert state == AuthState.WAITING_CODE
    assert "Invalid verification code" in msg
