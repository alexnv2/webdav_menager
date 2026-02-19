# core/config.py
"""Configuration management for WebDAV Manager."""

import base64
import binascii
import json
import logging
import os
import shutil
import sys
from typing import Optional, Dict, Any, List

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


def get_data_dir() -> str:
    """
    Get directory for storing configuration.

    Returns:
        Path to config directory
    """
    # В режиме разработки используем папку config в корне проекта
    if not getattr(sys, 'frozen', False):
        # Running as script (development mode)
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_dir = os.path.join(base_dir, 'config')
        return config_dir

    # В скомпилированной версии используем AppData
    appdata = os.environ.get('APPDATA')
    if appdata:
        return os.path.join(appdata, 'WebDAVManager')
    else:
        # Fallback to executable directory
        return os.path.join(os.path.dirname(sys.executable), 'config')


class ConfigManager:
    """Manager for application configuration and accounts."""

    # Default settings
    DEFAULT_SETTINGS = {
        'logs_enabled': True,
        'log_level': 'INFO',
        'theme': 'dark',
        'auto_connect': False,
        'confirm_on_exit': True,
        'cache_ttl': 300,
        'cache_size': 100,
        'auto_refresh': True,
        'refresh_interval': 30,
        'show_hidden': False,
        'download_folder': '',
        'temp_folder': '',
        'clean_temp': False,
        'language': 'ru',
        'font_size': 9,
        'icon_size': 16,
        'connection_timeout': 30,
        'read_timeout': 60,
        'retry_count': 3,
        'retry_delay': 2,
        'proxy_enabled': False,
        'proxy_type': 'http',
        'proxy_host': '',
        'proxy_port': 8080,
        'proxy_login': '',
        'proxy_password': '',
        'cache_enabled': True,
        'encryption_enabled': False,
        'encryption_delete_original': False
    }

    def __init__(self, config_dir: Optional[str] = None):
        """
        Initialize configuration manager.

        Args:
            config_dir: Custom configuration directory (optional)
        """
        self.config_dir = config_dir or get_data_dir()
        self.config_file = os.path.join(self.config_dir, "settings.json")
        self.accounts_file = os.path.join(self.config_dir, "accounts.json")

        # Create directory if it doesn't exist
        os.makedirs(self.config_dir, exist_ok=True)
        logger.debug(f"Config directory: {self.config_dir}")
        logger.debug(f"Config file: {self.config_file}")
        logger.debug(f"Accounts file: {self.accounts_file}")

        # Load configuration
        self.config = self._load_config()

        # Initialize settings
        if 'settings' not in self.config:
            self.config['settings'] = self.DEFAULT_SETTINGS.copy()

        self.settings = self.config['settings']

        # Initialize cipher for encryption
        self.cipher = self._init_cipher()

        # Load accounts
        self.accounts = self._load_accounts()

        # Log accounts info
        if self.accounts:
            logger.info(f"Loaded {len(self.accounts)} accounts")
            if isinstance(self.accounts, dict):
                logger.debug(f"Account names: {list(self.accounts.keys())}")
        else:
            logger.debug("No accounts loaded")

        logger.debug(
            f"ConfigManager initialized with config dir: {self.config_dir}")

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.debug(f"Loaded config from {self.config_file}")
                    return data
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Error loading configuration: {e}")
                return {}
        else:
            logger.debug(f"Configuration file not found: {self.config_file}")
            return {}

    def _save_config(self):
        """Save configuration to file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.config_file), exist_ok=True)

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)

            logger.debug(f"Configuration saved to {self.config_file}")

        except IOError as e:
            logger.error(f"Error saving configuration: {e}")

    def _init_cipher(self) -> Fernet:
        """Initialize Fernet cipher for encryption."""
        encryption_key = self.config.get('encryption_key')

        if not encryption_key:
            # Generate new key
            key = Fernet.generate_key()
            self.config['encryption_key'] = key.decode()
            self._save_config()
            return Fernet(key)

        try:
            # Validate existing key
            if isinstance(encryption_key, str):
                # Check if it's a valid Fernet key
                if len(encryption_key) == 44 and encryption_key.endswith('='):
                    try:
                        key_bytes = encryption_key.encode()
                        base64.urlsafe_b64decode(key_bytes)
                        return Fernet(key_bytes)
                    except (binascii.Error, ValueError):
                        logger.warning(
                            "Invalid encryption key, generating new one")
                        return self._generate_new_key()
                else:
                    logger.warning(
                        "Invalid encryption key length, generating new one")
                    return self._generate_new_key()
            else:
                return Fernet(encryption_key)

        except Exception as e:
            logger.error(f"Error loading encryption key: {e}")
            return self._generate_new_key()

    def _generate_new_key(self) -> Fernet:
        """Generate new encryption key."""
        key = Fernet.generate_key()
        self.config['encryption_key'] = key.decode()
        self._save_config()
        return Fernet(key)

    def _load_accounts(self) -> Dict[str, Any]:
        """Load accounts from encrypted file."""
        if not os.path.exists(self.accounts_file):
            logger.debug(f"Accounts file not found: {self.accounts_file}")
            return {}

        try:
            file_size = os.path.getsize(self.accounts_file)
            logger.debug(
                f"Accounts file exists: {self.accounts_file} (size: {file_size} bytes)")

            with open(self.accounts_file, 'rb') as f:
                encrypted_data = f.read()

            if not encrypted_data:
                logger.warning("Accounts file is empty")
                return {}

            try:
                decrypted_data = self.cipher.decrypt(encrypted_data)
                accounts = json.loads(decrypted_data.decode('utf-8'))

                logger.info(f"Successfully loaded {len(accounts)} accounts")
                return accounts

            except Exception as e:
                logger.error(f"Error decrypting accounts: {e}")
                self._backup_corrupted_file()
                return {}

        except IOError as e:
            logger.error(f"Error reading accounts file: {e}")
            return {}

    def _backup_corrupted_file(self):
        """Create backup of corrupted accounts file."""
        try:
            if os.path.exists(self.accounts_file):
                backup_file = self.accounts_file + '.corrupted.' + str(
                    int(os.path.getmtime(self.accounts_file)))
                shutil.copy2(self.accounts_file, backup_file)
                logger.info(f"Corrupted file backed up to {backup_file}")
        except Exception as e:
            logger.error(f"Error backing up corrupted file: {e}")

    def _save_accounts(self):
        """Save accounts to encrypted file."""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.accounts_file), exist_ok=True)

            data = json.dumps(self.accounts, ensure_ascii=False).encode(
                'utf-8')
            encrypted_data = self.cipher.encrypt(data)

            with open(self.accounts_file, 'wb') as f:
                f.write(encrypted_data)

            logger.debug(f"Accounts saved to {self.accounts_file}")

        except Exception as e:
            logger.error(f"Error saving accounts: {e}")
            raise

    # Public methods for settings management

    def save_config(self):
        """Save current configuration."""
        self.config['settings'] = self.settings
        self._save_config()

    def update_settings(self, **kwargs):
        """Update multiple settings at once."""
        self.settings.update(kwargs)
        self.save_config()

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get setting value by key."""
        return self.settings.get(key, default)

    def set_setting(self, key: str, value: Any):
        """Set single setting value."""
        self.settings[key] = value
        self.save_config()

    def set_theme(self, theme_name: str) -> bool:
        """Set theme (dark/light)."""
        if theme_name in ['dark', 'light']:
            self.settings['theme'] = theme_name
            self.save_config()
            return True
        return False

    # Public methods for account management

    def load_accounts(self) -> List[Dict[str, Any]]:
        """Load accounts as list of dictionaries."""
        logger.debug(f"Loading accounts, current type: {type(self.accounts)}")

        if isinstance(self.accounts, dict):
            logger.debug(f"Accounts is dict with {len(self.accounts)} items")
            result = list(self.accounts.values())
            logger.debug(f"Converted to list with {len(result)} items")
            return result
        elif isinstance(self.accounts, list):
            logger.debug(f"Accounts is list with {len(self.accounts)} items")
            return self.accounts
        else:
            logger.warning(
                f"Accounts is unexpected type: {type(self.accounts)}")
            return []

    def save_accounts(self, accounts: List[Dict[str, Any]]):
        """Save accounts from list of dictionaries."""
        logger.info(f"Saving {len(accounts)} accounts")

        # Очищаем текущие аккаунты
        new_accounts = {}

        # Преобразуем список в словарь
        for i, acc in enumerate(accounts):
            if isinstance(acc, dict):
                name = acc.get('name')
                if name:
                    # Убедимся, что все необходимые поля есть
                    normalized_acc = {
                        'name': name,
                        'url': acc.get('url', ''),
                        'login': acc.get('login', ''),
                        'password': acc.get('password', ''),
                        'type': acc.get('type', 'webdav'),
                        'default_path': acc.get('default_path', '/'),
                        'enabled': acc.get('enabled', True)
                    }
                    # Сохраняем id если есть
                    if 'id' in acc:
                        normalized_acc['id'] = acc['id']

                    new_accounts[name] = normalized_acc
                    logger.debug(f"Added account: {name}")
                else:
                    logger.warning(f"Account {i} missing name: {acc}")
            else:
                logger.warning(f"Account {i} is not a dict: {type(acc)}")

        self.accounts = new_accounts
        logger.info(f"Converted to dict with {len(new_accounts)} items")
        self._save_accounts()

    def get_account(self, name: str) -> Optional[Dict[str, Any]]:
        """Get account by name (password encrypted)."""
        if isinstance(self.accounts, dict):
            return self.accounts.get(name)
        return None

    def get_account_with_decrypted_password(self, name: str) -> Optional[
        Dict[str, Any]]:
        """Get account with decrypted password."""
        account = self.get_account(name)
        if account:
            try:
                account = account.copy()
                account['password'] = self.decrypt_password(
                    account['password'])
                return account
            except Exception as e:
                logger.error(
                    f"Error decrypting password for account '{name}': {e}")
                return None
        return None

    def save_account(self, name: str, url: str, login: str, password: str,
                     account_type: str = 'webdav', default_path: str = '/',
                     enabled: bool = True) -> bool:
        """Save single account."""
        try:
            # Check if password is already encrypted
            is_encrypted = False
            try:
                if password:
                    self.cipher.decrypt(password.encode('utf-8'))
                    is_encrypted = True
            except:
                pass

            encrypted_password = password if is_encrypted else self.encrypt_password(
                password)

            # Ensure accounts is dict
            if not isinstance(self.accounts, dict):
                self.accounts = {}

            # Create or update account
            self.accounts[name] = {
                'name': name,
                'url': url,
                'login': login,
                'password': encrypted_password,
                'type': account_type,
                'default_path': default_path,
                'enabled': enabled
            }

            self._save_accounts()
            logger.info(f"Account '{name}' saved successfully")
            return True

        except Exception as e:
            logger.error(f"Error saving account '{name}': {e}")
            return False

    def delete_account(self, name: str) -> bool:
        """Delete account by name."""
        if isinstance(self.accounts, dict) and name in self.accounts:
            del self.accounts[name]
            self._save_accounts()
            logger.info(f"Account '{name}' deleted")
            return True
        return False

    # Encryption methods

    def encrypt_password(self, password: str) -> str:
        """Encrypt password."""
        if not password:
            return ""
        try:
            return self.cipher.encrypt(password.encode('utf-8')).decode(
                'utf-8')
        except Exception as e:
            logger.error(f"Error encrypting password: {e}")
            return ""

    def decrypt_password(self, encrypted_password: str) -> str:
        """Decrypt password."""
        if not encrypted_password:
            return ""
        try:
            return self.cipher.decrypt(
                encrypted_password.encode('utf-8')).decode('utf-8')
        except Exception as e:
            logger.error(f"Error decrypting password: {e}")
            raise