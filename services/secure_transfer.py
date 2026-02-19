# services/secure_transfer.py
"""Secure file transfer with encryption."""

import os
import tempfile
import logging
import shutil
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal

from core.encryption import FileEncryptor
from core.key_manager import KeyManager
from core.client import WebDAVClient

logger = logging.getLogger(__name__)


class SecureTransferService(QObject):
    """Service for encrypted file transfer."""

    # Сигналы для связи с основным потоком
    operation_completed = pyqtSignal(str)
    operation_error = pyqtSignal(str)
    progress_updated = pyqtSignal(int, int)

    # Расширение для зашифрованных файлов
    ENCRYPTED_EXTENSION = '.encrypted'

    def __init__(self, client: WebDAVClient, key_manager: KeyManager,
                 encryptor: FileEncryptor):
        """
        Initialize secure transfer service.

        Args:
            client: WebDAV client
            key_manager: Key manager instance
            encryptor: File encryptor with active key
        """
        super().__init__()
        self.client = client
        self.key_manager = key_manager
        self.encryptor = encryptor
        self.temp_dir = tempfile.mkdtemp(prefix="webdav_secure_")

        # Save key if not already saved
        self._ensure_key_saved()

        logger.info(
            f"Secure transfer service initialized with temp dir: {self.temp_dir}")
        logger.info(
            f"Active key: {encryptor.key.name} (ID: {encryptor.key.id[:8]})")

    def _ensure_key_saved(self):
        """Ensure current key is saved in key manager."""
        key_info = self.encryptor.key.to_dict()
        if not self.key_manager.get_key(key_info['id']):
            self.key_manager.save_key(key_info)
            logger.info(f"Key saved to key manager: {key_info['id'][:8]}")

    def get_encrypted_remote_path(self, original_path: str) -> str:
        """Get remote path for encrypted file."""
        if original_path.endswith(self.ENCRYPTED_EXTENSION):
            return original_path
        return original_path + self.ENCRYPTED_EXTENSION

    def get_decrypted_local_path(self, encrypted_path: str) -> str:
        """Get local path for decrypted file."""
        if encrypted_path.endswith(self.ENCRYPTED_EXTENSION):
            return encrypted_path[:-len(self.ENCRYPTED_EXTENSION)]
        return encrypted_path

    def is_encrypted_file(self, file_path: str) -> bool:
        """
        Check if file is encrypted by looking for magic bytes.

        Args:
            file_path: Path to file

        Returns:
            True if file is encrypted with our format
        """
        try:
            if not os.path.exists(file_path):
                return False

            with open(file_path, 'rb') as f:
                magic = f.read(len(self.encryptor.MAGIC))
                return magic == self.encryptor.MAGIC
        except:
            return False

    def upload_encrypted(self, local_path: str, remote_path: str,
                         delete_original: bool = False) -> bool:
        """
        Upload file with encryption.
        """
        temp_file = None
        try:
            encrypted_remote = self.get_encrypted_remote_path(remote_path)
            temp_file = os.path.join(self.temp_dir,
                                     os.path.basename(local_path) + '.enc')

            logger.info(f"Encrypting {local_path} -> {temp_file}")

            def progress_callback(current, total):
                self.progress_updated.emit(current, total)

            success, message = self.encryptor.encrypt_file(
                local_path, temp_file, progress_callback
            )

            if not success:
                raise Exception(message)

            logger.info(f"Uploading encrypted file to {encrypted_remote}")
            self.client.upload_file(temp_file, encrypted_remote)

            if delete_original and os.path.exists(local_path):
                os.unlink(local_path)

            self.progress_updated.emit(100, 100)
            self.operation_completed.emit(
                f"Загружено: {os.path.basename(local_path)}")

            logger.info(
                f"Secure upload completed: {local_path} -> {encrypted_remote}")
            return True

        except Exception as e:
            logger.exception(f"Error in secure upload: {e}")
            error_msg = str(e)
            if "ключ" in error_msg.lower() or "key" in error_msg.lower():
                error_msg = "Ошибка шифрования: неверный ключ"
            self.operation_error.emit(error_msg)
            return False
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass

    def download_decrypted(self, remote_path: str, local_path: str,
                           delete_remote: bool = False) -> bool:
        """
        Download and decrypt file.
        """
        temp_file = None
        try:
            # Ensure remote path has encrypted extension
            if not remote_path.endswith(self.ENCRYPTED_EXTENSION):
                remote_path = self.get_encrypted_remote_path(remote_path)

            # Get local path without encrypted extension
            local_path = self.get_decrypted_local_path(local_path)
            temp_file = os.path.join(self.temp_dir,
                                     os.path.basename(remote_path))

            logger.info(f"Downloading encrypted file from {remote_path}")
            self.client.download_file(remote_path, temp_file)

            # Check if downloaded file is actually encrypted
            if not self.is_encrypted_file(temp_file):
                # File is not encrypted, just copy it
                logger.warning(
                    f"File {remote_path} is not encrypted, copying as-is")
                shutil.copy2(temp_file, local_path)

                if delete_remote:
                    self.client.delete(remote_path)

                self.progress_updated.emit(100, 100)
                self.operation_completed.emit(
                    f"Скачано: {os.path.basename(local_path)}")
                return True

            logger.info(f"Decrypting {temp_file} -> {local_path}")

            def progress_callback(current, total):
                self.progress_updated.emit(current, total)

            success, message = self.encryptor.decrypt_file(
                temp_file, local_path, progress_callback
            )

            if not success:
                raise Exception(message)

            if delete_remote:
                self.client.delete(remote_path)

            self.progress_updated.emit(100, 100)
            self.operation_completed.emit(
                f"Скачано: {os.path.basename(local_path)}")

            logger.info(
                f"Secure download completed: {remote_path} -> {local_path}")
            return True

        except Exception as e:
            logger.exception(f"Error in secure download: {e}")
            error_msg = str(e)
            if "ключ" in error_msg.lower() or "key" in error_msg.lower():
                error_msg = "Ошибка расшифровки: неверный ключ шифрования"
            elif "не является зашифрованным" in error_msg.lower():
                error_msg = "Файл не является зашифрованным"
            self.operation_error.emit(error_msg)
            return False
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except:
                    pass

    def cleanup(self):
        """Clean up temporary directory."""
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
            logger.info(f"Temporary directory cleaned up: {self.temp_dir}")