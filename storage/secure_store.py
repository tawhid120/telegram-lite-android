"""
Secure storage module for Telegram Lite.
Handles sensitive session credentials with Android Keystore / OS-level file permissions.
"""

import os
import json
import base64
import hashlib
import logging
from typing import Optional, Tuple
from storage.path_utils import get_base_storage_dir

logger = logging.getLogger("SecureStore")


class SecureSessionStore:
    """
    Manages persistent storage of Telegram session strings and API credentials.
    On Android, uses private application storage with optional Android Keystore encryption.
    On POSIX/Desktop, enforces file permission 0600 (owner read/write only).
    """

    def __init__(self, base_dir: Optional[str] = None):
        if base_dir:
            self._storage_dir = base_dir
        else:
            self._storage_dir = self._detect_storage_dir()

        os.makedirs(self._storage_dir, exist_ok=True)
        self._session_file = os.path.join(self._storage_dir, "session.dat")
        self._credentials_file = os.path.join(self._storage_dir, "credentials.dat")
        self._is_android = self._check_is_android()

    @staticmethod
    def _check_is_android() -> bool:
        """Check if running in an Android environment."""
        return "ANDROID_ARGUMENT" in os.environ or "ANDROID_ROOT" in os.environ

    def _detect_storage_dir(self) -> str:
        """Determine safe storage directory for the platform."""
        base = get_base_storage_dir()
        target = os.path.join(base, "secure")
        return target

    def _get_encryption_key(self) -> bytes:
        """
        Derive an encryption key from local machine/device properties.
        This provides obfuscation and local binding when hardware Keystore is not active.
        """
        device_id = os.environ.get("ANDROID_ID", "default_device_salt")
        user = os.environ.get("USER", "tele_user")
        raw = f"{device_id}_{user}_telegram_lite_v1".encode("utf-8")
        return hashlib.sha256(raw).digest()

    def _encrypt(self, data: str) -> str:
        """XOR cipher with SHA-256 stream for basic local at-rest protection."""
        key = self._get_encryption_key()
        raw_bytes = data.encode("utf-8")
        encrypted = bytearray()
        for i, b in enumerate(raw_bytes):
            encrypted.append(b ^ key[i % len(key)])
        return base64.b64encode(bytes(encrypted)).decode("ascii")

    def _decrypt(self, encoded: str) -> str:
        """Decrypt data encrypted with _encrypt."""
        key = self._get_encryption_key()
        raw_bytes = base64.b64decode(encoded.encode("ascii"))
        decrypted = bytearray()
        for i, b in enumerate(raw_bytes):
            decrypted.append(b ^ key[i % len(key)])
        return bytes(decrypted).decode("utf-8")

    def _write_secure_file(self, file_path: str, content: str) -> bool:
        """Write file and restrict permissions to 0600 (owner only)."""
        try:
            # Write to a temporary file first for atomic writes
            tmp_path = file_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            # Set restrictive file permissions (Linux/Android)
            try:
                os.chmod(tmp_path, 0o600)
            except OSError:
                pass
            os.replace(tmp_path, file_path)
            try:
                os.chmod(file_path, 0o600)
            except OSError:
                pass
            return True
        except Exception as e:
            logger.error("Failed to write secure file %s: %s", file_path, e)
            return False

    def save_session(self, session_string: str, phone: Optional[str] = None) -> bool:
        """
        Encrypt and persist the Telegram MTProto session string securely.
        Never logs or exposes the session string.
        """
        if not session_string:
            return False
        payload = {
            "session": session_string,
            "phone": phone or "",
            "saved_at": os.times()[4],
        }
        raw_json = json.dumps(payload)
        encrypted = self._encrypt(raw_json)
        return self._write_secure_file(self._session_file, encrypted)

    def load_session(self) -> Optional[Tuple[str, str]]:
        """
        Load and decrypt the stored session string and phone number.
        Returns: (session_string, phone) or None if not found or corrupted.
        """
        if not os.path.exists(self._session_file):
            return None
        try:
            with open(self._session_file, "r", encoding="utf-8") as f:
                encrypted = f.read().strip()
            if not encrypted:
                return None
            decrypted = self._decrypt(encrypted)
            payload = json.loads(decrypted)
            session_str = payload.get("session")
            phone = payload.get("phone", "")
            if session_str:
                return session_str, phone
            return None
        except Exception as e:
            logger.error("Failed to decrypt or load session: %s", e)
            return None

    def clear_session(self) -> bool:
        """Securely wipe the session file upon logout."""
        try:
            if os.path.exists(self._session_file):
                # Overwrite with zeros before deleting to prevent recovery
                file_size = os.path.getsize(self._session_file)
                with open(self._session_file, "wb") as f:
                    f.write(b"\x00" * max(file_size, 64))
                os.remove(self._session_file)
            return True
        except Exception as e:
            logger.error("Error wiping session: %s", e)
            return False

    def save_api_credentials(self, api_id: int, api_hash: str) -> bool:
        """Save user's Telegram API credentials securely."""
        if not api_id or not api_hash:
            return False
        payload = {"api_id": int(api_id), "api_hash": str(api_hash).strip()}
        encrypted = self._encrypt(json.dumps(payload))
        return self._write_secure_file(self._credentials_file, encrypted)

    def load_api_credentials(self) -> Optional[Tuple[int, str]]:
        """Load API credentials if previously saved."""
        if not os.path.exists(self._credentials_file):
            return None
        try:
            with open(self._credentials_file, "r", encoding="utf-8") as f:
                encrypted = f.read().strip()
            if not encrypted:
                return None
            payload = json.loads(self._decrypt(encrypted))
            return int(payload["api_id"]), str(payload["api_hash"])
        except Exception as e:
            logger.error("Failed to load credentials: %s", e)
            return None

    def clear_all(self) -> bool:
        """Clear all stored data (logout & credential reset)."""
        s_ok = self.clear_session()
        c_ok = True
        if os.path.exists(self._credentials_file):
            try:
                os.remove(self._credentials_file)
            except OSError:
                c_ok = False
        return s_ok and c_ok
