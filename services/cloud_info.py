# services/cloud_info.py
"""Cloud information service."""

import logging
import xml.etree.ElementTree as ET
from typing import Optional, Dict, Tuple
from functools import lru_cache
from datetime import datetime, timedelta

import requests
from requests.auth import HTTPBasicAuth

from core.client import WebDAVClient

logger = logging.getLogger(__name__)


class CloudInfoFetcher:
    """Service for fetching cloud storage information."""

    # Cache for quota information
    _quota_cache: Dict[str, Tuple[datetime, Dict]] = {}
    _cache_ttl = timedelta(minutes=5)

    @classmethod
    def _get_cache_key(cls, client: WebDAVClient) -> str:
        """Get cache key for client."""
        account = client.account
        if account:
            return f"{account.get('id', '')}:{account.get('url', '')}"
        return ""

    @classmethod
    def _get_cached_quota(cls, cache_key: str) -> Optional[Dict]:
        """Get cached quota if not expired."""
        if cache_key in cls._quota_cache:
            timestamp, quota = cls._quota_cache[cache_key]
            if datetime.now() - timestamp < cls._cache_ttl:
                return quota
            else:
                del cls._quota_cache[cache_key]
        return None

    @classmethod
    def _cache_quota(cls, cache_key: str, quota: Dict):
        """Cache quota information."""
        cls._quota_cache[cache_key] = (datetime.now(), quota)

    @classmethod
    def get_quota(cls, client: WebDAVClient, use_cache: bool = True) -> \
    Optional[Dict[str, int]]:
        """
        Get quota information from WebDAV server.

        Returns:
            Dictionary with 'used', 'available', 'total' keys or None if not available
        """
        if not client or not client.is_connected:
            logger.warning("Cannot get quota: client not connected")
            return None

        account = client.account
        if not account:
            return None

        # Check cache
        cache_key = cls._get_cache_key(client)
        if use_cache and cache_key:
            cached = cls._get_cached_quota(cache_key)
            if cached:
                logger.debug("Using cached quota")
                return cached

        try:
            quota = cls._fetch_quota(account)

            # Cache the result
            if quota and cache_key:
                cls._cache_quota(cache_key, quota)

            return quota

        except Exception as e:
            logger.exception(f"Error fetching quota: {e}")
            return None

    @classmethod
    def _fetch_quota(cls, account: Dict) -> Optional[Dict[str, int]]:
        """Fetch quota from server."""
        url = account['url'].rstrip('/') + '/'

        headers = {
            'Depth': '0',
            'Content-Type': 'application/xml'
        }

        body = '''<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
    <D:prop>
        <D:quota-used-bytes/>
        <D:quota-available-bytes/>
    </D:prop>
</D:propfind>'''

        session = requests.Session()
        session.auth = HTTPBasicAuth(account['login'], account['password'])

        response = session.request(
            'PROPFIND',
            url,
            data=body,
            headers=headers,
            timeout=30
        )

        if response.status_code != 207:  # Multi-Status
            logger.warning(f"Unexpected response code: {response.status_code}")
            return None

        tree = ET.fromstring(response.content)
        ns = {'D': 'DAV:'}

        used_elem = tree.find('.//D:quota-used-bytes', ns)
        avail_elem = tree.find('.//D:quota-available-bytes', ns)

        if used_elem is not None and avail_elem is not None:
            used = int(used_elem.text)
            available = int(avail_elem.text)
            total = used + available

            logger.info(
                f"Quota: used={used}, available={available}, total={total}")

            return {
                'used': used,
                'available': available,
                'total': total
            }

        logger.warning("Server did not return quota properties")
        return None

    @classmethod
    def clear_cache(cls):
        """Clear quota cache."""
        cls._quota_cache.clear()
        logger.debug("Quota cache cleared")

    @classmethod
    def get_server_info(cls, client: WebDAVClient) -> Optional[Dict]:
        """Get server information."""
        if not client or not client.is_connected:
            return None

        account = client.account
        if not account:
            return None

        try:
            url = account['url'].rstrip('/') + '/'

            headers = {
                'Depth': '0',
                'Content-Type': 'application/xml'
            }

            body = '''<?xml version="1.0" encoding="utf-8" ?>
<D:propfind xmlns:D="DAV:">
    <D:prop>
        <D:displayname/>
        <D:getcontenttype/>
        <D:creationdate/>
        <D:getlastmodified/>
    </D:prop>
</D:propfind>'''

            session = requests.Session()
            session.auth = HTTPBasicAuth(account['login'], account['password'])

            response = session.request(
                'PROPFIND',
                url,
                data=body,
                headers=headers,
                timeout=30
            )

            if response.status_code != 207:
                return None

            tree = ET.fromstring(response.content)
            ns = {'D': 'DAV:'}

            info = {}

            displayname = tree.find('.//D:displayname', ns)
            if displayname is not None and displayname.text:
                info['displayname'] = displayname.text

            return info

        except Exception as e:
            logger.exception(f"Error getting server info: {e}")
            return None