"""Shared HTTP utility with caching, retries, and provenance integration."""

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from synera_core.config import find_repo_root
from synera_core.provenance.manifest import register_file
from synera_core.provenance.ledger import Ledger

# Rate limiting could be simple sleep between requests or using a semaphore
# Tenacity handles retries, httpx handles the request.
# Let's set a global default User-Agent.

USER_AGENT = "SYNERA/0.1 (research; contact in README)"

class HTTPClient:
    """HTTP client with caching, retries, and ledger registration."""
    
    def __init__(self, cache_dir: Optional[Path] = None, ledger: Optional[Ledger] = None):
        if cache_dir is None:
            self.cache_dir = find_repo_root() / "data" / "raw" / "cache"
        else:
            self.cache_dir = cache_dir
            
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ledger = ledger
        
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
            follow_redirects=True,
        )

    def _get_cache_key(self, url: str, params: Optional[Dict[str, Any]] = None) -> str:
        """Generate a deterministic cache key for a URL and params."""
        key_str = url
        if params:
            # Sort params for determinism
            sorted_params = sorted(params.items())
            key_str += "?" + urlencode(sorted_params)
        return hashlib.sha256(key_str.encode("utf-8")).hexdigest()

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
    )
    def _fetch_with_retry(self, url: str, params: Optional[Dict[str, Any]] = None) -> bytes:
        """Fetch URL with retries."""
        response = self.client.get(url, params=params)
        response.raise_for_status()
        return response.content

    def get(self, url: str, params: Optional[Dict[str, Any]] = None, 
            force_refresh: bool = False) -> Tuple[bytes, Path, bool]:
        """
        GET request with raw-response caching and ledger registration.
        
        Returns:
            Tuple of (response_bytes, cache_file_path, was_cached)
        """
        cache_key = self._get_cache_key(url, params)
        cache_path = self.cache_dir / f"{cache_key}.raw"
        
        was_cached = cache_path.exists()
        
        if not force_refresh and was_cached:
            content = cache_path.read_bytes()
        else:
            content = self._fetch_with_retry(url, params)
            cache_path.write_bytes(content)
            
            # Register in ledger
            if self.ledger:
                register_file(
                    ledger=self.ledger,
                    path=cache_path,
                    kind="raw_data",
                    meta={"url": url, "params": params, "provenance": "REAL"}
                )
                
        return content, cache_path, was_cached

    def get_json(self, url: str, params: Optional[Dict[str, Any]] = None, 
                 force_refresh: bool = False) -> Tuple[Dict[str, Any], Path, bool]:
        """GET request returning parsed JSON."""
        content, cache_path, was_cached = self.get(url, params, force_refresh)
        return json.loads(content.decode("utf-8")), cache_path, was_cached
