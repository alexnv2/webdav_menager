# core/client.py
"""WebDAV client with async operations and caching."""

import os
import logging
import time
from typing import Optional, List, Dict, Any, Type
from urllib.parse import urljoin

import requests
from webdav3.client import Client
from webdav3.exceptions import WebDavException

from PyQt5.QtCore import QObject, pyqtSignal, QThread

from core.cache import Cache
from core.models import FileInfo
from utils.helpers import format_error

logger = logging.getLogger(__name__)


class WebDAVClient(QObject):
    """WebDAV client with async operations and caching."""

    # Signals
    list_finished = pyqtSignal(str, list)  # path, files
    list_error = pyqtSignal(str, str)  # path, error
    operation_finished = pyqtSignal(str)  # message
    operation_error = pyqtSignal(str)  # error
    progress = pyqtSignal(int, int)  # current, total

    def __init__(self, cache_ttl: int = 300, cache_size: int = 100):
        super().__init__()
        self._client: Optional[Client] = None
        self._account: Optional[Dict] = None
        self._cache = Cache(cache_ttl, cache_size)
        self._workers: List[QThread] = []
        self._max_retries: int = 3
        self._retry_delay: int = 2

        logger.info(
            f"WebDAVClient initialized with cache_ttl={cache_ttl}, cache_size={cache_size}")

    def set_account(self, account: Dict[str, str]):
        """Set current account and initialize client."""
        self._account = account

        options = {
            'webdav_hostname': account['url'].rstrip('/'),
            'webdav_login': account['login'],
            'webdav_password': account['password'],
            'webdav_timeout': account.get('timeout', 30)
        }

        self._client = Client(options)
        self._cache.clear()

        # Update retry settings
        self._max_retries = account.get('retry_count', 3)
        self._retry_delay = account.get('retry_delay', 2)

        logger.info(
            f"Account set: {account.get('name', 'unknown')} with timeout={options['webdav_timeout']}s")

    def update_settings(self, settings: Dict[str, Any]):
        """Update client settings."""
        self._max_retries = settings.get('retry_count', 3)
        self._retry_delay = settings.get('retry_delay', 2)

    @property
    def is_connected(self) -> bool:
        """Check if client is connected."""
        return self._client is not None

    @property
    def account(self) -> Optional[Dict]:
        """Get current account."""
        return self._account

    def _get_cache_key(self, path: str) -> str:
        """Generate cache key for path."""
        if not self._account:
            return path
        return f"{self._account.get('id', '')}:{path}"

    def _execute_with_retry(self, operation: str, func, *args, **kwargs):
        """Execute operation with retry logic."""
        last_error = None

        for attempt in range(self._max_retries):
            try:
                logger.info(
                    f"Executing {operation} (attempt {attempt + 1}/{self._max_retries})")
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"{operation} attempt {attempt + 1} failed: {e}")

                if attempt < self._max_retries - 1:
                    wait_time = self._retry_delay * (attempt + 1)
                    logger.info(f"Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                else:
                    logger.exception(f"All {operation} attempts failed")

        raise WebDavException(
            f"Ошибка {operation} после {self._max_retries} попыток: {format_error(last_error)}")

    def list_files(self, path: str = "/", use_cache: bool = True,
                   as_dict: bool = False) -> List[Any]:
        """List files in directory."""
        if not self._client:
            raise WebDavException("Клиент не инициализирован")

        cache_key = self._get_cache_key(path)

        # Try cache first
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"Using cached data for {path}")
                return cached

        # Execute with retry
        files = self._execute_with_retry(
            "list", self._client.list, path, get_info=True
        )

        logger.info(f"Received {len(files)} items from {path}")

        # Convert to FileInfo objects
        result = [FileInfo.from_webdav_info(f) for f in files]

        if use_cache:
            self._cache.set(cache_key, result)

        # Return as dicts if requested
        if as_dict:
            return [f.to_dict() for f in result]

        return result

    def list_files_no_cache(self, path: str = "/") -> List[FileInfo]:
        """List files without using cache."""
        return self.list_files(path, use_cache=False)

    def download_file(self, remote_path: str, local_path: str):
        """Download file synchronously."""
        if not self._client:
            raise WebDavException("Клиент не инициализирован")

        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(local_path), exist_ok=True)

        self._execute_with_retry(
            "download", self._client.download_sync, remote_path, local_path
        )

        logger.info(f"Successfully downloaded {remote_path}")

    def upload_file(self, local_path: str, remote_path: str):
        """Upload file synchronously."""
        if not self._client or not self._account:
            raise WebDavException("Клиент не инициализирован")

        if not os.path.exists(local_path):
            raise FileNotFoundError(f"Файл не найден: {local_path}")

        file_size = os.path.getsize(local_path)

        # Use requests for upload
        url = urljoin(self._account['url'].rstrip('/'), remote_path)

        with open(local_path, 'rb') as f:
            auth = (self._account['login'], self._account['password'])

            def _upload():
                response = requests.put(
                    url,
                    data=f,
                    auth=auth,
                    headers={'Content-Type': 'application/octet-stream'},
                    timeout=60
                )
                if response.status_code not in (200, 201, 204):
                    raise WebDavException(f"HTTP {response.status_code}")
                return response

            self._execute_with_retry("upload", _upload)

        logger.info(f"Successfully uploaded {local_path} ({file_size} bytes)")

        # Invalidate cache for parent directory
        parent = os.path.dirname(remote_path) or '/'
        self._cache.remove(self._get_cache_key(parent))

    def move(self, src_path: str, dst_path: str):
        """Move/rename file or directory."""
        if not self._client:
            raise WebDavException("Клиент не инициализирован")

        self._execute_with_retry("move", self._client.move, src_path, dst_path)

        logger.info(f"Successfully moved {src_path} -> {dst_path}")
        self._invalidate_after_move(src_path, dst_path)

    def copy(self, src_path: str, dst_path: str):
        """Copy file or directory."""
        if not self._client:
            raise WebDavException("Клиент не инициализирован")

        self._execute_with_retry("copy", self._client.copy, src_path, dst_path)

        logger.info(f"Successfully copied {src_path} -> {dst_path}")

        # Invalidate cache for destination parent
        parent = os.path.dirname(dst_path) or '/'
        self._cache.remove(self._get_cache_key(parent))

    def delete(self, path: str):
        """Delete file or directory."""
        if not self._client:
            raise WebDavException("Клиент не инициализирован")

        self._execute_with_retry("delete", self._client.clean, path)

        logger.info(f"Successfully deleted {path}")

        # Invalidate cache
        parent = os.path.dirname(path) or '/'
        self._cache.remove(self._get_cache_key(parent))

    def mkdir(self, path: str):
        """Create directory."""
        if not self._client:
            raise WebDavException("Клиент не инициализирован")

        self._execute_with_retry("mkdir", self._client.mkdir, path)

        logger.info(f"Successfully created directory {path}")

        # Invalidate cache for parent
        parent = os.path.dirname(path) or '/'
        self._cache.remove(self._get_cache_key(parent))

    def _invalidate_after_move(self, src: str, dst: str):
        """Invalidate cache after move operation."""
        src_parent = os.path.dirname(src) or '/'
        dst_parent = os.path.dirname(dst) or '/'

        self._cache.remove(self._get_cache_key(src_parent))
        if src_parent != dst_parent:
            self._cache.remove(self._get_cache_key(dst_parent))

    # Async methods
    def list_files_async(self, path: str = "/"):
        """List files asynchronously."""
        self._create_worker(ListWorker, path)

    def download_async(self, remote_path: str, local_path: str):
        """Download file asynchronously."""
        self._create_worker(DownloadWorker, remote_path, local_path)

    def upload_async(self, local_path: str, remote_path: str):
        """Upload file asynchronously."""
        self._create_worker(UploadWorker, local_path, remote_path)

    def move_async(self, src_path: str, dst_path: str):
        """Move file asynchronously."""
        self._create_worker(MoveWorker, src_path, dst_path)

    def copy_async(self, src_path: str, dst_path: str):
        """Copy file asynchronously."""
        self._create_worker(CopyWorker, src_path, dst_path)

    def delete_async(self, path: str):
        """Delete file asynchronously."""
        self._create_worker(DeleteWorker, path)

    def mkdir_async(self, path: str):
        """Create directory asynchronously."""
        self._create_worker(MkdirWorker, path)

    def rename_async(self, old_path: str, new_path: str):
        """Rename file asynchronously."""
        self._create_worker(RenameWorker, old_path, new_path)

    def _create_worker(self, worker_class, *args):
        """Create and start a worker."""
        worker = worker_class(self, *args)
        worker.finished.connect(lambda result: self._on_worker_finished(worker, result))
        worker.error.connect(lambda err: self._on_worker_error(worker, err))
        worker.finished.connect(worker.deleteLater)
        worker.error.connect(worker.deleteLater)
        worker.start()
        self._workers.append(worker)
        logger.debug(f"Started worker: {worker_class.__name__}")

    def _on_worker_finished(self, worker, result):
        """Handle worker finished."""
        if worker in self._workers:
            self._workers.remove(worker)

        # Emit appropriate signal
        if hasattr(worker, 'path') and hasattr(worker, 'get_files'):
            self.list_finished.emit(worker.path, result)
        else:
            self.operation_finished.emit(result)

        logger.debug(f"Worker finished: {worker.__class__.__name__}")

    def _on_worker_error(self, worker, error):
        """Handle worker error."""
        if worker in self._workers:
            self._workers.remove(worker)

        # Determine signal type
        if hasattr(worker, 'path'):
            self.list_error.emit(getattr(worker, 'path', '/'), error)
        else:
            self.operation_error.emit(format_error(error))

        logger.error(f"Worker error: {worker.__class__.__name__}: {error}")

    def cancel_all_operations(self):
        """Cancel all running operations."""
        for worker in self._workers[:]:  # Create a copy
            if worker.isRunning():
                worker.terminate()
                worker.wait(1000)
                self._workers.remove(worker)
        logger.info("All operations cancelled")


class BaseWorker(QThread):
    """Base worker class for async operations."""

    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, client: WebDAVClient):
        super().__init__()
        self.client = client


class ListWorker(BaseWorker):
    """Worker for listing files."""

    def __init__(self, client: WebDAVClient, path: str):
        super().__init__(client)
        self.path = path

    def run(self):
        try:
            files = self.client.list_files(self.path, as_dict=True)
            self.finished.emit(files)
        except Exception as e:
            self.error.emit(str(e))


class DownloadWorker(BaseWorker):
    """Worker for downloading files."""

    def __init__(self, client: WebDAVClient, remote: str, local: str):
        super().__init__(client)
        self.remote = remote
        self.local = local

    def run(self):
        try:
            self.client.download_file(self.remote, self.local)
            self.finished.emit(f"Скачано: {os.path.basename(self.remote)}")
        except Exception as e:
            self.error.emit(str(e))


class UploadWorker(BaseWorker):
    """Worker for uploading files."""

    def __init__(self, client: WebDAVClient, local: str, remote: str):
        super().__init__(client)
        self.local = local
        self.remote = remote

    def run(self):
        try:
            self.client.upload_file(self.local, self.remote)
            self.finished.emit(f"Загружено: {os.path.basename(self.local)}")
        except Exception as e:
            self.error.emit(str(e))


class MoveWorker(BaseWorker):
    """Worker for moving files."""

    def __init__(self, client: WebDAVClient, src: str, dst: str):
        super().__init__(client)
        self.src = src
        self.dst = dst

    def run(self):
        try:
            self.client.move(self.src, self.dst)
            self.finished.emit(f"Перемещено: {os.path.basename(self.src)}")
        except Exception as e:
            self.error.emit(str(e))


class CopyWorker(BaseWorker):
    """Worker for copying files."""

    def __init__(self, client: WebDAVClient, src: str, dst: str):
        super().__init__(client)
        self.src = src
        self.dst = dst

    def run(self):
        try:
            self.client.copy(self.src, self.dst)
            self.finished.emit(f"Скопировано: {os.path.basename(self.src)}")
        except Exception as e:
            self.error.emit(str(e))


class DeleteWorker(BaseWorker):
    """Worker for deleting files."""

    def __init__(self, client: WebDAVClient, path: str):
        super().__init__(client)
        self.path = path

    def run(self):
        try:
            self.client.delete(self.path)
            self.finished.emit(f"Удалено: {os.path.basename(self.path)}")
        except Exception as e:
            self.error.emit(str(e))


class MkdirWorker(BaseWorker):
    """Worker for creating directories."""

    def __init__(self, client: WebDAVClient, path: str):
        super().__init__(client)
        self.path = path

    def run(self):
        try:
            self.client.mkdir(self.path)
            self.finished.emit(f"Папка создана: {os.path.basename(self.path)}")
        except Exception as e:
            self.error.emit(str(e))


class RenameWorker(BaseWorker):
    """Worker for renaming files."""

    def __init__(self, client: WebDAVClient, old_path: str, new_path: str):
        super().__init__(client)
        self.old_path = old_path
        self.new_path = new_path

    def run(self):
        try:
            self.client.move(self.old_path, self.new_path)
            self.finished.emit(
                f"Переименовано в: {os.path.basename(self.new_path)}")
        except Exception as e:
            self.error.emit(str(e))