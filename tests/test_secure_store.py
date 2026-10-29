"""
Tests for SecureSessionStore.
Validates session persistence, encryption, loading, and safe wiping on logout.
"""

import os
import tempfile
import shutil
from storage.secure_store import SecureSessionStore


def test_session_save_and_load():
    tmp_dir = tempfile.mkdtemp()
    try:
        store = SecureSessionStore(base_dir=tmp_dir)
        dummy_session = "1BVtsOMQBu7...dummy_mtproto_string_session..."
        dummy_phone = "+1234567890"

        # Initially no session
        assert store.load_session() is None

        # Save session
        ok = store.save_session(dummy_session, dummy_phone)
        assert ok is True

        # Verify session file exists
        session_file = os.path.join(tmp_dir, "session.dat")
        assert os.path.exists(session_file)

        # File content must NOT be plaintext session string
        with open(session_file, "r") as f:
            raw = f.read()
            assert dummy_session not in raw

        # Load session
        loaded = store.load_session()
        assert loaded is not None
        loaded_str, loaded_phone = loaded
        assert loaded_str == dummy_session
        assert loaded_phone == dummy_phone

        # Logout / clear session
        store.clear_session()
        assert store.load_session() is None
        assert not os.path.exists(session_file)
    finally:
        shutil.rmtree(tmp_dir)


def test_api_credentials_storage():
    tmp_dir = tempfile.mkdtemp()
    try:
        store = SecureSessionStore(base_dir=tmp_dir)
        api_id = 1234567
        api_hash = "abcdef0123456789abcdef0123456789"

        assert store.load_api_credentials() is None

        ok = store.save_api_credentials(api_id, api_hash)
        assert ok is True

        loaded = store.load_api_credentials()
        assert loaded is not None
        assert loaded == (api_id, api_hash)

        store.clear_all()
        assert store.load_api_credentials() is None
    finally:
        shutil.rmtree(tmp_dir)


def test_storage_path_utils():
    from storage.path_utils import get_base_storage_dir
    base = get_base_storage_dir()
    assert os.path.exists(base)
    assert os.path.isdir(base)
    # Verify write access
    probe = os.path.join(base, ".test_probe")
    with open(probe, "w") as f:
        f.write("test")
    assert os.path.exists(probe)
    os.remove(probe)


def test_app_config_default_credentials():
    from app.config import AppConfig
    store = SecureSessionStore(base_dir=tempfile.mkdtemp())
    config = AppConfig(store, config_path="/nonexistent/config.json")
    api_id, api_hash = config.get_api_credentials()
    assert api_id == 20193909
    assert api_hash == "82cd035fc1eb439bda68b2bfc75a57cb"
