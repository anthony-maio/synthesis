"""
Exchange client for communicating with the Live Exchange server.

Handles searching, downloading, and publishing capabilities.
"""

from typing import Any, Dict, List, Optional

import httpx

from synthesis.core.models import CapabilityCategory


class ExchangeClient:
    """Client for the Synthesis Live Exchange"""

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
    ):
        """
        Initialize exchange client.

        Args:
            base_url: Base URL of the exchange server
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=timeout,
            headers={"User-Agent": "Synthesis-Client/0.3.0"},
        )

    async def search(
        self,
        query: str,
        category: Optional[CapabilityCategory] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Search for capabilities on the exchange.

        Args:
            query: Search query
            category: Optional category filter
            limit: Maximum results to return

        Returns:
            List of matching capability summaries
        """
        params = {"q": query, "limit": limit}
        if category:
            params["category"] = category.value

        try:
            response = await self.client.get("/search", params=params)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return []

    async def download(self, capability_id: str) -> Optional[Dict[str, Any]]:
        """
        Download a capability from the exchange.

        Args:
            capability_id: ID of the capability to download

        Returns:
            Full capability data or None if not found
        """
        try:
            response = await self.client.get(f"/download/{capability_id}")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return None

    async def publish(
        self,
        name: str,
        description: str,
        code: str,
        tests: List[Dict[str, Any]],
        dependencies: List[str] = None,
    ) -> Dict[str, Any]:
        """
        Publish a capability to the exchange.

        Args:
            name: Capability name
            description: What it does
            code: Implementation code
            tests: Test cases
            dependencies: Required packages

        Returns:
            Publication result with status and ID
        """
        payload = {
            "name": name,
            "description": description,
            "code": code,
            "tests": tests,
            "dependencies": dependencies or [],
        }

        try:
            response = await self.client.post("/publish", json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            return {"status": "error", "error": str(e)}

    async def get_stats(self) -> Dict[str, Any]:
        """Get exchange statistics."""
        try:
            response = await self.client.get("/stats")
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError:
            return {}

    async def health_check(self) -> bool:
        """Check if the exchange is reachable."""
        try:
            response = await self.client.get("/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    async def close(self) -> None:
        """Close the client connection."""
        await self.client.aclose()

    async def __aenter__(self) -> "ExchangeClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
