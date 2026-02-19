# core/master_key.py
"""Master key management for application access."""

import os
import json
import base64
import logging
from typing import Optional, Tuple
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class MasterKeyManager:
    """Manages master key for application access."""

    def __init__(self, config_dir: str):
        """
        Initialize master key manager.

        Args:
            config_dir: Directory to store master key data
        """
        self.config_dir = config_dir
        self.master_key_file = os.path.join(config_dir, '.master_key.bin')
        self.salt_file = os.path.join(config_dir, '.master_salt.bin')
        self.backup_file = os.path.join(config_dir, '.master_key.backup')

        # Create directory if not exists
        os.makedirs(config_dir, exist_ok=True)

        self._master_key: Optional[bytes] = None
        self._salt: Optional[bytes] = None

    def is_initialized(self) -> bool:
        """Check if master key is already set up."""
        return os.path.exists(self.master_key_file) and os.path.exists(
            self.salt_file)

    def is_configured(self) -> bool:
        """Alias for is_initialized."""
        return self.is_initialized()

    def create_master_key(self, password: str) -> Tuple[bool, str]:
        """
        Create new master key from password.

        Args:
            password: Master password

        Returns:
            Tuple of (success, message)
        """
        try:
            # Generate random salt
            salt = os.urandom(32)

            # Derive key using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=200000,  # Higher iterations for master key
                backend=default_backend()
            )
            key = kdf.derive(password.encode('utf-8'))

            # Save salt
            with open(self.salt_file, 'wb') as f:
                f.write(salt)
            os.chmod(self.salt_file, 0o600)

            # Save key (encrypted with itself for validation)
            cipher = Fernet(base64.urlsafe_b64encode(key))
            encrypted_key = cipher.encrypt(b"VALIDATION_TOKEN")

            with open(self.master_key_file, 'wb') as f:
                f.write(encrypted_key)
            os.chmod(self.master_key_file, 0o600)

            # Create backup
            with open(self.backup_file, 'wb') as f:
                f.write(encrypted_key)
            os.chmod(self.backup_file, 0o600)

            logger.info("Master key created successfully")
            return True, "Мастер-ключ успешно создан"

        except Exception as e:
            logger.error(f"Failed to create master key: {e}")
            return False, f"Ошибка создания мастер-ключа: {e}"

    def verify_password(self, password: str) -> bool:
        """
        Verify master password.

        Args:
            password: Password to verify

        Returns:
            True if password is correct
        """
        try:
            if not self.is_initialized():
                return False

            # Load salt
            with open(self.salt_file, 'rb') as f:
                salt = f.read()

            # Derive key from provided password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=200000,
                backend=default_backend()
            )
            key = kdf.derive(password.encode('utf-8'))

            # Try to decrypt stored key
            cipher = Fernet(base64.urlsafe_b64encode(key))

            with open(self.master_key_file, 'rb') as f:
                encrypted = f.read()

            # If decryption succeeds, password is correct
            cipher.decrypt(encrypted)
            return True

        except Exception as e:
            logger.warning(f"Password verification failed: {e}")
            return False

    def change_password(self, old_password: str, new_password: str) -> Tuple[
        bool, str]:
        """
        Change master password.

        Args:
            old_password: Current password
            new_password: New password

        Returns:
            Tuple of (success, message)
        """
        try:
            # Verify old password
            if not self.verify_password(old_password):
                return False, "Неверный текущий пароль"

            # Load salt
            with open(self.salt_file, 'rb') as f:
                salt = f.read()

            # Derive old key
            kdf_old = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=200000,
                backend=default_backend()
            )
            old_key = kdf_old.derive(old_password.encode('utf-8'))

            # Load existing encrypted data
            with open(self.master_key_file, 'rb') as f:
                encrypted = f.read()

            # Decrypt with old key
            cipher_old = Fernet(base64.urlsafe_b64encode(old_key))
            data = cipher_old.decrypt(encrypted)

            # Generate new salt
            new_salt = os.urandom(32)

            # Derive new key
            kdf_new = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=new_salt,
                iterations=200000,
                backend=default_backend()
            )
            new_key = kdf_new.derive(new_password.encode('utf-8'))

            # Re-encrypt data with new key
            cipher_new = Fernet(base64.urlsafe_b64encode(new_key))
            new_encrypted = cipher_new.encrypt(data)

            # Save new salt
            with open(self.salt_file, 'wb') as f:
                f.write(new_salt)

            # Save new encrypted key
            with open(self.master_key_file, 'wb') as f:
                f.write(new_encrypted)

            # Update backup
            with open(self.backup_file, 'wb') as f:
                f.write(new_encrypted)

            logger.info("Master password changed successfully")
            return True, "Пароль успешно изменен"

        except Exception as e:
            logger.error(f"Failed to change password: {e}")
            return False, f"Ошибка изменения пароля: {e}"

    def reset_from_backup(self, password: str) -> Tuple[bool, str]:
        """
        Reset master key from backup using password.

        Args:
            password: Password to verify

        Returns:
            Tuple of (success, message)
        """
        try:
            if not os.path.exists(self.backup_file):
                return False, "Резервная копия не найдена"

            # Try to verify with backup
            with open(self.salt_file, 'rb') as f:
                salt = f.read()

            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=200000,
                backend=default_backend()
            )
            key = kdf.derive(password.encode('utf-8'))

            cipher = Fernet(base64.urlsafe_b64encode(key))

            with open(self.backup_file, 'rb') as f:
                encrypted = f.read()

            # If decryption succeeds, restore backup
            cipher.decrypt(encrypted)

            # Copy backup to main file
            import shutil
            shutil.copy2(self.backup_file, self.master_key_file)

            logger.info("Master key restored from backup")
            return True, "Мастер-ключ восстановлен из резервной копии"

        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return False, "Не удалось восстановить ключ из резервной копии"

    def restore_from_backup(self, backup_file: str, new_password: str) -> \
            Tuple[bool, str]:
        """
        Restore master key from backup file and set new password.

        Args:
            backup_file: Path to back up file
            new_password: New password to set

        Returns:
            Tuple of (success, message)
        """
        try:
            if not os.path.exists(backup_file):
                return False, "Файл резервной копии не найден"

            # Generate new salt
            new_salt = os.urandom(32)

            # Derive new key from new password
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=new_salt,
                iterations=200000,
                backend=default_backend()
            )
            new_key = kdf.derive(new_password.encode('utf-8'))

            # Read the backup file
            with open(backup_file, 'rb') as f:
                backup_data = f.read()

            # Create validation token
            validation_data = b"VALIDATION_TOKEN"

            # Encrypt with new key
            cipher_new = Fernet(base64.urlsafe_b64encode(new_key))
            new_encrypted = cipher_new.encrypt(validation_data)

            # Save the new encrypted data as master key
            with open(self.master_key_file, 'wb') as f:
                f.write(new_encrypted)
            os.chmod(self.master_key_file, 0o600)

            # Save the new salt
            with open(self.salt_file, 'wb') as f:
                f.write(new_salt)
            os.chmod(self.salt_file, 0o600)

            # Also save as backup
            with open(self.backup_file, 'wb') as f:
                f.write(new_encrypted)
            os.chmod(self.backup_file, 0o600)

            logger.info("Master key restored from backup with new password")
            return True, ("Мастер-ключ восстановлен из резервной копии. Новый "
                          "пароль установлен.")

        except Exception as e:
            logger.error(f"Failed to restore from backup: {e}")
            return False, f"Ошибка восстановления из резервной копии: {e}"