"""
Application Configuration and API Credential Management for Telegram Lite.
Safely resolves credentials without embedding secrets in version control.
"""

import os
import json
import logging
from typing import Optional, Tuple, Any
from storage.secure_store import SecureSessionStore
from storage.path_utils import get_base_storage_dir

logger = logging.getLogger("AppConfig")


class AppConfig:
    """
    Configuration manager for Telegram Lite.
    Order of credential resolution:
    1. Environment variables (TG_API_ID, TG_API_HASH)
    2. Secure stored credentials (saved by user in setup screen)
    3. Optional local config.json (ignored by git)
    """

    DEFAULT_APP_NAME = "Telegram Lite"
    VERSION = "0.1.1"

    # User-configured default API credentials
    DEFAULT_API_ID = 20193909
    DEFAULT_API_HASH = "82cd035fc1eb439bda68b2bfc75a57cb"

    def __init__(self, secure_store: SecureSessionStore, config_path: Optional[str] = None):
        self.secure_store = secure_store
        self.config_path = config_path or os.path.join(get_base_storage_dir(), "config.json")
        self.low_resource_mode = False
        self.dark_mode = True

    def get_api_credentials(self) -> Tuple[Optional[int], Optional[str]]:
        """
        Resolve API ID and API Hash safely from environment, secure store, config file,
        or pre-configured default credentials.
        Returns: (api_id, api_hash)
        """
        # 1. Environment variables (supports API_ID, TG_API_ID, TELEGRAM_API_ID)
        env_id = (
            os.environ.get("API_ID")
            or os.environ.get("TG_API_ID")
            or os.environ.get("TELEGRAM_API_ID")
        )
        env_hash = (
            os.environ.get("API_HASH")
            or os.environ.get("TG_API_HASH")
            or os.environ.get("TELEGRAM_API_HASH")
        )
        if env_id and env_hash:
            try:
                return int(env_id.strip()), env_hash.strip()
            except ValueError:
                pass

        # 2. Secure Store
        saved = self.secure_store.load_api_credentials()
        if saved:
            return saved[0], saved[1]

        # 3. Local config.json
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    c_id = data.get("api_id")
                    c_hash = data.get("api_hash")
                    if c_id and c_hash:
                        return int(c_id), str(c_hash).strip()
            except Exception as e:
                logger.warning("Could not read config.json: %s", e)

        # 4. Built-in pre-configured defaults
        if self.DEFAULT_API_ID and self.DEFAULT_API_HASH:
            return self.DEFAULT_API_ID, self.DEFAULT_API_HASH

        return None, None

    def save_api_credentials(self, api_id: int, api_hash: str) -> bool:
        """Persist API credentials into secure storage."""
        if not self.validate_credentials(api_id, api_hash):
            return False
        return self.secure_store.save_api_credentials(api_id, api_hash)

    @staticmethod
    def validate_credentials(api_id: Any, api_hash: str) -> bool:
        """Validate API ID is positive integer and API Hash is non-empty string."""
        try:
            val_id = int(api_id)
            if val_id <= 0:
                return False
        except (ValueError, TypeError):
            return False

        if not api_hash or not isinstance(api_hash, str) or len(api_hash.strip()) < 10:
            return False

        return True
