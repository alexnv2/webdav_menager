# core/webdav_client.py
"""Simple WebDAV client for connection testing."""

import logging
from typing import Optional, Tuple
from urllib.parse import urljoin

import requests
from requests.auth import HTTPBasicAuth
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)


class WebDAVClient:
    """Simple WebDAV client for testing connections."""

    def __init__(self, base_url: str, username: str, password: str,
                 timeout: int = 10):
        """
        Initialize WebDAV client.

        Args:
            base_url: WebDAV server URL
            username: Login username
            password: Login password
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip('/')
        self.username = username
        self.password = password
        self.timeout = timeout

        # Create session for connection reuse
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(username, password)
        self.session.headers.update({
            'User-Agent': 'FileBridge/1.0',
            'Accept': '*/*'
        })

    def check_connection(self) -> bool:
        """
        Check if connection to WebDAV server is working.

        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Try to access root directory
            response = self._make_request('PROPFIND', self.base_url + '/')

            # Check if response is successful (2xx status code)
            return 200 <= response.status_code < 300

        except RequestException as e:
            logger.error(f"Connection check failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during connection check: {e}")
            return False

    def test_connection(self) -> Tuple[bool, str]:
        """
        Test connection and return detailed result.

        Returns:
            Tuple[bool, str]: (success, message)
        """
        try:
            response = self._make_request('PROPFIND', self.base_url + '/')

            if response.status_code == 200:
                return True, "Подключение успешно!"
            elif response.status_code == 201:
                return True, "Ресурс создан, подключение работает"
            elif response.status_code == 207:
                return True, "Мультистатус ответ, подключение работает"
            elif response.status_code == 401:
                return False, "Ошибка авторизации: неверный логин или пароль"
            elif response.status_code == 404:
                return False, "URL не найден. Проверьте адрес сервера"
            elif response.status_code >= 500:
                return False, f"Ошибка сервера (HTTP {response.status_code})"
            else:
                return False, f"Неожиданный ответ сервера: HTTP {response.status_code}"

        except requests.ConnectionError:
            return False, "Не удалось подключиться к серверу. Проверьте URL и сетевое соединение"
        except requests.Timeout:
            return False, "Превышено время ожидания ответа от сервера"
        except requests.RequestException as e:
            return False, f"Ошибка запроса: {str(e)}"
        except Exception as e:
            return False, f"Неизвестная ошибка: {str(e)}"

    def _make_request(self, method: str, url: str,
                      **kwargs) -> requests.Response:
        """
        Make HTTP request with proper WebDAV headers.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional arguments for requests

        Returns:
            requests.Response: Server response
        """
        # Add WebDAV specific headers
        headers = kwargs.pop('headers', {})
        if method.upper() == 'PROPFIND':
            headers['Depth'] = '0'
            headers['Content-Type'] = 'application/xml'

        # Merge with session headers
        request_headers = self.session.headers.copy()
        request_headers.update(headers)

        # Make request
        response = self.session.request(
            method=method,
            url=url,
            headers=request_headers,
            timeout=self.timeout,
            allow_redirects=True,
            **kwargs
        )

        return response

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Альтернативная простая версия без создания отдельного класса
def test_webdav_connection(url: str, login: str, password: str,
                           timeout: int = 10) -> Tuple[bool, str]:
    """
    Simple function to test WebDAV connection.

    Args:
        url: WebDAV server URL
        login: Login username
        password: Login password
        timeout: Request timeout in seconds

    Returns:
        Tuple[bool, str]: (success, message)
    """
    try:
        # Ensure URL ends with slash for root access
        base_url = url.rstrip('/') + '/'

        # Make PROPFIND request to root
        response = requests.request(
            method='PROPFIND',
            url=base_url,
            auth=HTTPBasicAuth(login, password),
            headers={
                'Depth': '0',
                'User-Agent': 'FileBridge/1.0'
            },
            timeout=timeout,
            allow_redirects=True
        )

        # Check response
        if response.status_code in (200, 201, 207, 301, 302):
            return True, "Подключение успешно!"
        elif response.status_code == 401:
            return False, "Ошибка авторизации: неверный логин или пароль"
        elif response.status_code == 404:
            return False, "URL не найден. Проверьте адрес сервера"
        elif response.status_code == 405:
            # Method not allowed - try simple GET as fallback
            return _test_with_get(url, login, password, timeout)
        else:
            return False, f"Ошибка HTTP {response.status_code}: {response.reason}"

    except requests.ConnectionError:
        return False, "Не удалось подключиться к серверу. Проверьте URL и сетевое соединение"
    except requests.Timeout:
        return False, "Превышено время ожидания ответа от сервера"
    except requests.RequestException as e:
        return False, f"Ошибка запроса: {str(e)}"
    except Exception as e:
        return False, f"Неизвестная ошибка: {str(e)}"


def _test_with_get(url: str, login: str, password: str, timeout: int) -> Tuple[
    bool, str]:
    """Fallback test using GET request."""
    try:
        base_url = url.rstrip('/') + '/'
        response = requests.get(
            base_url,
            auth=HTTPBasicAuth(login, password),
            timeout=timeout
        )

        if response.status_code == 200:
            return True, "Подключение успешно (режим совместимости)"
        else:
            return False, f"Ошибка HTTP {response.status_code}"
    except:
        return False, "Сервер не поддерживает WebDAV методы"