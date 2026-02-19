# core/encryption.py
"""AES encryption module for file security with adaptive chunk sizing."""

import base64
import logging
import os
import time
import platform
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Tuple, Callable, Dict, Any

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


@dataclass
class EncryptionKey:
    """Encryption key information."""
    id: str
    key: bytes
    salt: bytes
    name: str = "default"
    created: Optional[str] = None
    password_derived: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'id': self.id,
            'name': self.name,
            'key': base64.b64encode(self.key).decode('utf-8'),
            'salt': base64.b64encode(self.salt).decode('utf-8'),
            'created': self.created,
            'password_derived': self.password_derived
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptionKey':
        """Create from dictionary."""
        return cls(
            id=data['id'],
            name=data.get('name', 'default'),
            key=base64.b64decode(data['key']),
            salt=base64.b64decode(data['salt']),
            created=data.get('created'),
            password_derived=data.get('password_derived', False)
        )


class ThrottledProgress:
    """Progress callback with throttling to avoid too frequent calls."""

    def __init__(self, callback: Optional[Callable], total: int,
                 min_interval: float = 0.1):
        """
        Initialize throttled progress.

        Args:
            callback: Progress callback function (current, total)
            total: Total size in bytes
            min_interval: Minimum time between callbacks in seconds
        """
        self.callback = callback
        self.total = total
        self.min_interval = min_interval
        self.last_call = 0
        self.last_value = 0
        self.last_percent = 0

    def update(self, current: int):
        """Update progress with throttling."""
        if not self.callback:
            return

        now = time.time()
        percent = (current / self.total) * 100 if self.total > 0 else 0

        # Call if: enough time passed, or significant progress, or completed
        time_passed = now - self.last_call >= self.min_interval
        significant_progress = percent - self.last_percent >= 5  # 5% change
        completed = current >= self.total

        if time_passed or significant_progress or completed:
            self.callback(current, self.total)
            self.last_call = now
            self.last_value = current
            self.last_percent = percent


class AdaptiveFileEncryptor:
    """AES encryption for files with adaptive chunk sizing for optimal performance."""

    # AES constants
    BLOCK_SIZE = 16
    KEY_SIZE = 32  # 256 bits
    MAGIC = b'WEBDAV_ENC_V2'

    # Base chunk size (will be adapted based on file size)
    BASE_CHUNK_SIZE = 64 * 1024  # 64KB base

    # Thresholds for adaptive sizing
    SMALL_FILE_THRESHOLD = 10 * 1024 * 1024  # 10MB
    MEDIUM_FILE_THRESHOLD = 100 * 1024 * 1024  # 100MB
    LARGE_FILE_THRESHOLD = 1024 * 1024 * 1024  # 1GB

    def __init__(self, key: Optional[EncryptionKey] = None):
        """
        Initialize encryptor with key.

        Args:
            key: Encryption key (required)
        """
        if not key:
            raise ValueError("Encryption key is required")

        self.key = key
        self.backend = default_backend()
        self._cipher_cache = {}
        self._system = platform.system()

        # Detect if we're on SSD (simplified - you might want more sophisticated detection)
        self._is_ssd = self._detect_storage_type()

        logger.info(
            f"Encryptor initialized with key: {key.name} (ID: {key.id[:8]})"
        )
        logger.info(
            f"System: {self._system}, Storage type: {'SSD' if self._is_ssd else 'HDD'}")

    def _detect_storage_type(self) -> bool:
        """Simplified storage type detection."""
        try:
            import psutil
            # If psutil is available, we could check disk rotations
            return True
        except:
            # Default to SSD for modern systems
            return True

    def get_optimal_chunk_size(self, file_size: int) -> int:
        """
        Select optimal chunk size based on file size and storage type.

        Args:
            file_size: Size of file in bytes

        Returns:
            Optimal chunk size in bytes
        """
        if file_size < self.SMALL_FILE_THRESHOLD:
            # Small files: smaller chunks to minimize memory overhead
            base = self.BASE_CHUNK_SIZE * 4  # 256KB
        elif file_size < self.MEDIUM_FILE_THRESHOLD:
            # Medium files: balance between memory and I/O
            base = self.BASE_CHUNK_SIZE * 16  # 1MB
        elif file_size < self.LARGE_FILE_THRESHOLD:
            # Large files: bigger chunks for throughput
            base = self.BASE_CHUNK_SIZE * 64  # 4MB
        else:
            # Huge files: very large chunks
            base = self.BASE_CHUNK_SIZE * 256  # 16MB

        # Adjust for storage type
        if not self._is_ssd:
            # For HDD, smaller chunks to avoid random access
            base = min(base, self.BASE_CHUNK_SIZE * 32)  # Max 2MB for HDD

        # Round to multiple of block size for efficiency
        base = (base // self.BLOCK_SIZE) * self.BLOCK_SIZE

        return base

    def get_optimal_buffer_size(self, chunk_size: int) -> int:
        """Get optimal I/O buffer size based on chunk size."""
        return max(chunk_size * 2,
                   1024 * 1024)  # At least 1MB, or 2x chunk size

    @classmethod
    def create_from_password(cls, password: str,
                             name: str = "password_key") -> 'AdaptiveFileEncryptor':
        """Create encryptor from password."""
        salt = os.urandom(16)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=cls.KEY_SIZE,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = kdf.derive(password.encode('utf-8'))

        encryption_key = EncryptionKey(
            id=os.urandom(8).hex(),
            key=key,
            salt=salt,
            name=name,
            created=datetime.now().isoformat(),
            password_derived=True
        )

        return cls(encryption_key)

    @classmethod
    def create_random(cls,
                      name: str = "random_key") -> 'AdaptiveFileEncryptor':
        """Create encryptor with random key."""
        salt = os.urandom(16)
        key = os.urandom(cls.KEY_SIZE)

        encryption_key = EncryptionKey(
            id=os.urandom(8).hex(),
            key=key,
            salt=salt,
            name=name,
            created=datetime.now().isoformat(),
            password_derived=False
        )

        return cls(encryption_key)

    def _preallocate_space(self, file_path: str, size: int):
        """
        Preallocate space for file to reduce fragmentation.

        Args:
            file_path: Path to file
            size: Size to preallocate in bytes
        """
        try:
            if self._system == 'Windows':
                # Windows preallocation
                import ctypes
                kernel32 = ctypes.windll.kernel32
                handle = kernel32.CreateFileW(
                    file_path,
                    0x10000000,  # GENERIC_WRITE
                    0,  # FILE_SHARE_READ
                    None,
                    2,  # CREATE_ALWAYS
                    0x80,  # FILE_ATTRIBUTE_NORMAL
                    None
                )
                if handle != -1:
                    kernel32.SetFilePointerEx(handle, size, None, 0)
                    kernel32.SetEndOfFile(handle)
                    kernel32.CloseHandle(handle)
            else:
                # Unix preallocation
                with open(file_path, 'wb') as f:
                    f.truncate(size)
        except Exception as e:
            logger.debug(f"Failed to preallocate space: {e}")
            # Non-critical, continue without preallocation

    def _process_file(self, input_path: str, output_path: str,
                      mode: str, progress_callback: Optional[Callable] = None,
                      iv: Optional[bytes] = None) -> Tuple[bool, str]:
        """
        Process file (encrypt or decrypt) with adaptive chunk sizing.

        Args:
            input_path: Source file path
            output_path: Output file path
            mode: 'encrypt' or 'decrypt'
            progress_callback: Progress callback
            iv: Initialization vector (for encryption)

        Returns:
            Tuple of (success, message)
        """
        try:
            if not os.path.exists(input_path):
                return False, f"Файл не найден: {input_path}"

            file_size = os.path.getsize(input_path)

            # Adaptive chunk size based on file size
            chunk_size = self.get_optimal_chunk_size(file_size)
            buffer_size = self.get_optimal_buffer_size(chunk_size)

            operation = "Encrypting" if mode == 'encrypt' else "Decrypting"
            logger.info(
                f"{operation} file: {input_path} ({file_size} bytes) "
                f"with chunk size: {chunk_size / 1024:.1f}KB"
            )

            os.makedirs(os.path.dirname(os.path.abspath(output_path)),
                        exist_ok=True)

            # Throttled progress
            progress = ThrottledProgress(progress_callback, file_size)

            if mode == 'encrypt':
                # Generate random IV for encryption
                iv = iv or os.urandom(self.BLOCK_SIZE)

                # Preallocate space for encrypted file (estimate)
                estimated_size = file_size + 1024  # + header and padding
                self._preallocate_space(output_path, estimated_size)

                # Setup encryption
                cipher = Cipher(algorithms.AES(self.key.key), modes.CBC(iv),
                                backend=self.backend)
                encryptor = cipher.encryptor()
                padder = padding.PKCS7(self.BLOCK_SIZE * 8).padder()

                # Write header with buffering
                with open(output_path, 'wb', buffering=buffer_size) as f_out:
                    f_out.write(self.MAGIC)
                    f_out.write(
                        self.key.id.encode('utf-8')[:8].ljust(8, b'\x00'))
                    f_out.write(iv)
                    f_out.write(self.key.salt)

                    processed = 0
                    # Use memoryview for efficient slicing
                    with open(input_path, 'rb', buffering=buffer_size) as f_in:
                        while True:
                            chunk = f_in.read(chunk_size)
                            if not chunk:
                                # Finalize padding
                                chunk = padder.finalize()
                                if chunk:
                                    encrypted = encryptor.update(chunk)
                                    f_out.write(encrypted)
                                break

                            # Pad and encrypt
                            padded = padder.update(chunk)
                            if padded:
                                encrypted = encryptor.update(padded)
                                f_out.write(encrypted)

                            processed += len(chunk)
                            progress.update(processed)

                    # Finalize
                    final = encryptor.finalize()
                    if final:
                        f_out.write(final)

            else:  # decrypt
                with open(input_path, 'rb', buffering=buffer_size) as f_in:
                    # Read and verify header
                    magic = f_in.read(len(self.MAGIC))
                    if magic != self.MAGIC:
                        return False, "Файл не является зашифрованным"

                    key_id = f_in.read(8).decode('utf-8').rstrip('\x00')
                    if key_id != self.key.id[:8]:
                        return False, "Неверный ключ шифрования"

                    iv = f_in.read(self.BLOCK_SIZE)
                    salt = f_in.read(16)

                    if len(iv) != self.BLOCK_SIZE or len(salt) != 16:
                        return False, "Неверный формат зашифрованного файла"

                    # Setup decryption
                    cipher = Cipher(algorithms.AES(self.key.key),
                                    modes.CBC(iv),
                                    backend=self.backend)
                    decryptor = cipher.decryptor()
                    unpadder = padding.PKCS7(self.BLOCK_SIZE * 8).unpadder()

                    # Preallocate space for decrypted file
                    self._preallocate_space(output_path, file_size)

                    with open(output_path, 'wb',
                              buffering=buffer_size) as f_out:
                        processed = 0

                        while True:
                            chunk = f_in.read(chunk_size)
                            if not chunk:
                                break

                            decrypted = decryptor.update(chunk)

                            if f_in.tell() == file_size:
                                # Last chunk - unpad
                                try:
                                    decrypted = unpadder.update(
                                        decrypted) + unpadder.finalize()
                                except Exception as e:
                                    return False, "Ошибка расшифровки: неверный ключ"
                            else:
                                decrypted = unpadder.update(decrypted)

                            f_out.write(decrypted)

                            processed += len(chunk)
                            progress.update(processed)

            logger.info(f"File {mode}ed successfully: {output_path}")
            return True, f"Файл успешно {'зашифрован' if mode == 'encrypt' else 'расшифрован'}"

        except PermissionError:
            return False, "Ошибка доступа к файлу"
        except Exception as e:
            logger.exception(f"Error {mode}ing file: {e}")
            return False, f"Ошибка {'шифрования' if mode == 'encrypt' else 'расшифровки'}: {e}"

    def encrypt_file(self, input_path: str, output_path: str,
                     progress_callback: Optional[Callable] = None) -> Tuple[
        bool, str]:
        """Encrypt a file with adaptive chunk sizing."""
        return self._process_file(input_path, output_path, 'encrypt',
                                  progress_callback)

    def decrypt_file(self, input_path: str, output_path: str,
                     progress_callback: Optional[Callable] = None) -> Tuple[
        bool, str]:
        """Decrypt a file with adaptive chunk sizing."""
        return self._process_file(input_path, output_path, 'decrypt',
                                  progress_callback)

    def is_encrypted(self, file_path: str) -> bool:
        """Check if file is encrypted with our format."""
        try:
            if not os.path.exists(file_path):
                return False
            with open(file_path, 'rb') as f:
                return f.read(len(self.MAGIC)) == self.MAGIC
        except:
            return False

    def get_file_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """
        Get encryption info from encrypted file.

        Args:
            file_path: Path to encrypted file

        Returns:
            Dictionary with file info or None if not encrypted
        """
        try:
            if not self.is_encrypted(file_path):
                return None

            with open(file_path, 'rb') as f:
                f.read(len(self.MAGIC))  # Skip magic
                key_id = f.read(8).decode('utf-8').rstrip('\x00')
                iv = f.read(self.BLOCK_SIZE)
                salt = f.read(16)

                return {
                    'key_id': key_id,
                    'iv': base64.b64encode(iv).decode('utf-8'),
                    'salt': base64.b64encode(salt).decode('utf-8'),
                    'file_size': os.path.getsize(file_path),
                    'data_offset': f.tell()
                }
        except Exception as e:
            logger.error(f"Failed to get file info: {e}")
            return None


# Convenience aliases for backward compatibility
FileEncryptor = AdaptiveFileEncryptor