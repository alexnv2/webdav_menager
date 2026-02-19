# test_master_key.py
"""Test master key functionality."""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.master_key import MasterKeyManager
from core.config import get_data_dir

logging.basicConfig(level=logging.INFO)


def test_master_key():
    """Test master key configuration."""
    config_dir = get_data_dir()
    print(f"Config directory: {config_dir}")

    master_key_manager = MasterKeyManager(config_dir)

    is_configured = master_key_manager.is_configured()
    print(f"Master key configured: {is_configured}")

    if is_configured:
        print("Master key files exist:")
        print(
            f"  - {master_key_manager.master_key_file}: {os.path.exists(master_key_manager.master_key_file)}")
        print(
            f"  - {master_key_manager.salt_file}: {os.path.exists(master_key_manager.salt_file)}")

        # Проверим размер файлов
        if os.path.exists(master_key_manager.master_key_file):
            size = os.path.getsize(master_key_manager.master_key_file)
            print(f"  Master key file size: {size} bytes")

        if os.path.exists(master_key_manager.salt_file):
            size = os.path.getsize(master_key_manager.salt_file)
            print(f"  Salt file size: {size} bytes")
    else:
        print("Master key not configured")


if __name__ == "__main__":
    test_master_key()