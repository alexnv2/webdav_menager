# core/key_manager.py
"""Key management for encryption."""

import json
import logging
import os
from typing import Optional, Dict, Any

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class KeyManager:
    """Manages encryption keys with secure storage."""

    def __init__(self, config_dir: str):
        """
        Initialize key manager.

        Args:
            config_dir: Directory to store keys
        """
        self.config_dir = config_dir
        self.keys_file = os.path.join(config_dir, 'encryption_keys.json')
        self.master_key_file = os.path.join(config_dir, '.master.key')
        self._master_key = None

        # Create config directory if it doesn't exist
        os.makedirs(config_dir, exist_ok=True)

        self._load_master_key()
        logger.info(f"KeyManager initialized with config dir: {config_dir}")

    def _generate_master_key(self) -> bytes:
        """Generate master key for encrypting other keys."""
        key = Fernet.generate_key()
        with open(self.master_key_file, 'wb') as f:
            f.write(key)
        # Set permissions to read-only for owner (Unix only)
        try:
            os.chmod(self.master_key_file, 0o600)
        except:
            pass  # Ignore on Windows
        logger.info("Generated new master key")
        return key

    def _load_master_key(self) -> bytes:
        """Load master key from file."""
        if os.path.exists(self.master_key_file):
            with open(self.master_key_file, 'rb') as f:
                self._master_key = f.read()
            logger.debug("Loaded master key from file")
        else:
            self._master_key = self._generate_master_key()
        return self._master_key

    def _get_cipher(self) -> Fernet:
        """Get Fernet cipher for key encryption."""
        if not self._master_key:
            self._load_master_key()
        return Fernet(self._master_key)

    def save_key(self, key_info: Dict[str, Any]) -> bool:
        """
        Save key to encrypted storage.

        Args:
            key_info: Key information dictionary

        Returns:
            True if successful
        """
        try:
            # Load existing keys
            keys = self._load_keys()

            # Add or update key
            key_id = key_info['id']
            keys[key_id] = key_info

            # Encrypt and save
            cipher = self._get_cipher()
            encrypted_data = cipher.encrypt(
                json.dumps(keys, ensure_ascii=False).encode('utf-8'))

            with open(self.keys_file, 'wb') as f:
                f.write(encrypted_data)

            # Set permissions (Unix only)
            try:
                os.chmod(self.keys_file, 0o600)
            except:
                pass

            logger.info(
                f"Key '{key_info.get('name', 'unknown')}' saved successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to save key: {e}")
            return False

    def _load_keys(self) -> Dict[str, Any]:
        """Load all keys from storage."""
        if not os.path.exists(self.keys_file):
            return {}

        try:
            with open(self.keys_file, 'rb') as f:
                encrypted_data = f.read()

            if not encrypted_data:
                return {}

            cipher = self._get_cipher()
            decrypted_data = cipher.decrypt(encrypted_data)
            return json.loads(decrypted_data.decode('utf-8'))

        except Exception as e:
            logger.error(f"Failed to load keys: {e}")
            return {}

    def get_key(self, key_id: Optional[str] = None,
                name: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get key by ID or name.

        Args:
            key_id: Key ID
            name: Key name

        Returns:
            Key information or None
        """
        keys = self._load_keys()

        if key_id and key_id in keys:
            return keys[key_id]

        if name:
            for key in keys.values():
                if key.get('name') == name:
                    return key

        return None

    def get_all_keys(self) -> Dict[str, Any]:
        """Get all keys."""
        return self._load_keys()

    def delete_key(self, key_id: str) -> bool:
        """
        Delete key by ID.

        Args:
            key_id: Key ID to delete

        Returns:
            True if successful
        """
        keys = self._load_keys()

        if key_id in keys:
            del keys[key_id]

            # Save updated keys
            cipher = self._get_cipher()
            encrypted_data = cipher.encrypt(
                json.dumps(keys, ensure_ascii=False).encode('utf-8'))

            with open(self.keys_file, 'wb') as f:
                f.write(encrypted_data)

            logger.info(f"Key {key_id} deleted")
            return True

        return False

    def import_key(self, key_data: Dict[str, Any]) -> Optional[str]:
        """
        Import key from external source.

        Args:
            key_data: Key data dictionary

        Returns:
            Key ID if successful
        """
        try:
            # Validate key data
            required_fields = ['id', 'key', 'salt', 'name']
            for field in required_fields:
                if field not in key_data:
                    raise ValueError(f"Missing field: {field}")

            # Save key
            if self.save_key(key_data):
                return key_data['id']

        except Exception as e:
            logger.error(f"Failed to import key: {e}")

        return None

    def export_key(self, key_id: str) -> Optional[Dict[str, Any]]:
        """
        Export key for backup.

        Args:
            key_id: Key ID to export

        Returns:
            Key data dictionary or None
        """
        key = self.get_key(key_id)
        if key:
            # Return a copy
            return key.copy()
        return None