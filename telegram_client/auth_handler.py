"""
MTProto Authentication Handler for Telegram Lite.
Implements the official Telegram login flow:
1. auth.sendCode (identifying in-app code delivery to active sessions vs SMS)
2. auth.signIn (verification code verification)
3. 2FA Two-Step Verification (auth.checkPassword)
4. Session persistence & secure logout
"""

import logging
from typing import Optional, Tuple
from telethon import TelegramClient
from telethon.tl import types
from telethon.errors import (
    SessionPasswordNeededError,
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeEmptyError,
    FloodWaitError,
    PasswordHashInvalidError,
    AuthKeyUnregisteredError,
    ApiIdInvalidError,
    UserDeactivatedError,
)

from telegram_client.models import AuthState, CodeDeliveryType, TelegramUser
from storage.secure_store import SecureSessionStore

logger = logging.getLogger("AuthHandler")


class AuthHandler:
    """
    Manages Telegram MTProto authentication flow state machine.
    """

    def __init__(self, secure_store: SecureSessionStore):
        self.secure_store = secure_store
        self.state = AuthState.UNAUTHENTICATED
        self.phone: Optional[str] = None
        self.phone_code_hash: Optional[str] = None
        self.delivery_type = CodeDeliveryType.UNKNOWN
        self.timeout_seconds: int = 60
        self.last_error: Optional[str] = None
        self.current_user: Optional[TelegramUser] = None

    def reset(self) -> None:
        """Reset authentication state."""
        self.state = AuthState.UNAUTHENTICATED
        self.phone = None
        self.phone_code_hash = None
        self.delivery_type = CodeDeliveryType.UNKNOWN
        self.timeout_seconds = 60
        self.last_error = None
        self.current_user = None

    async def send_code(
        self, client: TelegramClient, phone_number: str
    ) -> Tuple[bool, str, CodeDeliveryType, int]:
        """
        Request authentication code from Telegram via MTProto auth.sendCode.
        Returns: (success: bool, message: str, delivery_type: CodeDeliveryType, timeout: int)
        """
        phone_cleaned = phone_number.strip().replace(" ", "").replace("-", "")
        if not phone_cleaned.startswith("+"):
            phone_cleaned = "+" + phone_cleaned

        self.phone = phone_cleaned
        self.last_error = None

        try:
            sent_code = await client.send_code_request(self.phone)
            self.phone_code_hash = sent_code.phone_code_hash
            self.timeout_seconds = getattr(sent_code, "timeout", 60) or 60

            # Inspect code delivery mechanism
            type_obj = sent_code.type
            if isinstance(type_obj, types.auth.SentCodeTypeApp):
                self.delivery_type = CodeDeliveryType.APP_IN_APP
                msg = (
                    "Login code sent to your active Telegram session (Desktop, Web, or another device). "
                    "Please check your Telegram service notifications from 'Telegram'."
                )
            elif isinstance(type_obj, types.auth.SentCodeTypeSms):
                self.delivery_type = CodeDeliveryType.SMS
                msg = "Login code sent via SMS to your phone."
            elif isinstance(type_obj, types.auth.SentCodeTypeCall):
                self.delivery_type = CodeDeliveryType.CALL
                msg = "Telegram will call you to deliver the verification code."
            elif isinstance(type_obj, types.auth.SentCodeTypeFlashCall):
                self.delivery_type = CodeDeliveryType.FLASH_CALL
                msg = "Incoming flash call verification initiated."
            elif isinstance(type_obj, getattr(types.auth, "SentCodeTypeFragmentSms", object)):
                self.delivery_type = CodeDeliveryType.FRAGMENT_SMS
                msg = "Code delivered via Fragment SMS."
            else:
                self.delivery_type = CodeDeliveryType.UNKNOWN
                msg = "Verification code requested. Please check Telegram or your phone."

            self.state = AuthState.WAITING_CODE
            return True, msg, self.delivery_type, self.timeout_seconds

        except PhoneNumberInvalidError:
            err = "Invalid phone number. Please check country code and formatting."
            self.last_error = err
            self.state = AuthState.ERROR
            return False, err, CodeDeliveryType.UNKNOWN, 0

        except FloodWaitError as e:
            wait_min = max(1, e.seconds // 60)
            err = f"Too many requests. Telegram rate limit in effect: wait {e.seconds}s (~{wait_min} min) before retrying."
            self.last_error = err
            self.state = AuthState.ERROR
            return False, err, CodeDeliveryType.UNKNOWN, e.seconds

        except ApiIdInvalidError:
            err = "Invalid API ID or API Hash. Please verify your Telegram developer credentials."
            self.last_error = err
            self.state = AuthState.ERROR
            return False, err, CodeDeliveryType.UNKNOWN, 0

        except Exception as e:
            err_str = str(e)
            if "PHONE_NUMBER_BANNED" in err_str:
                err = "This phone number has been banned by Telegram."
            elif "SMS_NOT_ALLOWED" in err_str or "SEND_CODE_UNAVAILABLE" in err_str:
                err = (
                    "Telegram has restricted SMS delivery for third-party clients on this account. "
                    "Make sure your Telegram account is logged into another device (Telegram Web or Desktop) "
                    "so the code can be delivered in-app for free."
                )
            else:
                err = f"Failed to send code: {err_str}"
            self.last_error = err
            self.state = AuthState.ERROR
            return False, err, CodeDeliveryType.UNKNOWN, 0

    async def sign_in_with_code(
        self, client: TelegramClient, code: str
    ) -> Tuple[bool, str, AuthState]:
        """
        Submit the verification code received via Telegram in-app or SMS.
        """
        code_cleaned = code.strip().replace(" ", "").replace("-", "")
        if not self.phone or not self.phone_code_hash:
            return False, "Session expired or code not requested yet. Please start over.", AuthState.ERROR

        try:
            await client.sign_in(
                phone=self.phone,
                code=code_cleaned,
                phone_code_hash=self.phone_code_hash,
            )
            # Successfully authenticated
            me = await client.get_me()
            self.current_user = TelegramUser(
                id=me.id,
                first_name=me.first_name or "",
                last_name=me.last_name,
                username=me.username,
                phone=me.phone,
            )
            # Persist session string
            session_str = client.session.save()
            self.secure_store.save_session(session_str, self.phone)
            self.state = AuthState.AUTHENTICATED
            return True, f"Welcome, {self.current_user.full_name}!", AuthState.AUTHENTICATED

        except SessionPasswordNeededError:
            # 2FA Two-Step Verification is active on this account
            self.state = AuthState.WAITING_PASSWORD_2FA
            return True, "Two-step verification password is required.", AuthState.WAITING_PASSWORD_2FA

        except PhoneCodeInvalidError:
            err = "Invalid verification code. Please check the code and try again."
            self.last_error = err
            return False, err, AuthState.WAITING_CODE

        except PhoneCodeExpiredError:
            err = "Verification code has expired. Please request a new code."
            self.last_error = err
            self.state = AuthState.UNAUTHENTICATED
            return False, err, AuthState.UNAUTHENTICATED

        except PhoneCodeEmptyError:
            err = "Verification code cannot be empty."
            self.last_error = err
            return False, err, AuthState.WAITING_CODE

        except FloodWaitError as e:
            err = f"Too many attempts. Rate limited for {e.seconds} seconds."
            self.last_error = err
            return False, err, AuthState.ERROR

        except Exception as e:
            err = f"Sign-in error: {str(e)}"
            self.last_error = err
            return False, err, AuthState.ERROR

    async def sign_in_with_password(
        self, client: TelegramClient, password: str
    ) -> Tuple[bool, str, AuthState]:
        """
        Authenticate with 2FA password (auth.checkPassword).
        """
        if self.state != AuthState.WAITING_PASSWORD_2FA:
            return False, "2FA password is not currently requested.", self.state

        try:
            await client.sign_in(password=password)
            me = await client.get_me()
            self.current_user = TelegramUser(
                id=me.id,
                first_name=me.first_name or "",
                last_name=me.last_name,
                username=me.username,
                phone=me.phone,
            )
            session_str = client.session.save()
            self.secure_store.save_session(session_str, self.phone)
            self.state = AuthState.AUTHENTICATED
            return True, f"Welcome, {self.current_user.full_name}!", AuthState.AUTHENTICATED

        except PasswordHashInvalidError:
            err = "Incorrect two-step verification password. Please try again."
            self.last_error = err
            return False, err, AuthState.WAITING_PASSWORD_2FA

        except FloodWaitError as e:
            err = f"Rate limited. Please wait {e.seconds} seconds before retrying password."
            self.last_error = err
            return False, err, AuthState.ERROR

        except Exception as e:
            err = f"Two-step verification failed: {str(e)}"
            self.last_error = err
            return False, err, AuthState.ERROR

    async def check_saved_session(
        self, client: TelegramClient
    ) -> Tuple[bool, Optional[TelegramUser]]:
        """
        Verify if an existing saved session is still valid on Telegram servers.
        """
        try:
            if not await client.is_user_authorized():
                self.state = AuthState.UNAUTHENTICATED
                return False, None

            me = await client.get_me()
            if not me:
                self.state = AuthState.UNAUTHENTICATED
                return False, None

            self.current_user = TelegramUser(
                id=me.id,
                first_name=me.first_name or "",
                last_name=me.last_name,
                username=me.username,
                phone=me.phone,
            )
            self.state = AuthState.AUTHENTICATED
            return True, self.current_user

        except (AuthKeyUnregisteredError, UserDeactivatedError):
            logger.warning("Session was revoked or expired on server.")
            self.secure_store.clear_session()
            self.state = AuthState.UNAUTHENTICATED
            return False, None
        except Exception as e:
            logger.error("Error verifying saved session: %s", e)
            self.state = AuthState.UNAUTHENTICATED
            return False, None

    async def logout(self, client: TelegramClient) -> bool:
        """
        Explicitly log out from Telegram server and wipe local credentials.
        """
        try:
            if client and client.is_connected() and await client.is_user_authorized():
                await client.log_out()
        except Exception as e:
            logger.warning("Could not execute server logout: %s", e)

        # Always wipe local session safely
        self.secure_store.clear_session()
        self.reset()
        return True
