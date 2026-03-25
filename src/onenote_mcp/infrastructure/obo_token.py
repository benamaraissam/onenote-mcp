"""Exchange an upstream access token for a Graph API token via Azure OBO flow."""

import logging
import time

import httpx

_log = logging.getLogger(__name__)

_cached_token: str = ""
_cached_expires_at: float = 0.0
_cached_assertion: str = ""

GRAPH_SCOPE = "https://graph.microsoft.com/.default"


async def exchange_obo_token(
    *,
    assertion: str,
    server_client_id: str,
    server_client_secret: str,
    tenant_id: str,
    scopes: str = GRAPH_SCOPE,
) -> str:
    """Exchange an mcp-access token for a Graph token using On-Behalf-Of flow.

    Uses App A (server) credentials to perform the exchange at Azure's token endpoint.
    Results are cached per-assertion until expiry.
    """
    global _cached_token, _cached_expires_at, _cached_assertion  # noqa: PLW0603

    if (
        _cached_token
        and _cached_assertion == assertion
        and time.time() < _cached_expires_at - 60
    ):
        return _cached_token

    url = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token"
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "client_id": server_client_id,
        "client_secret": server_client_secret,
        "assertion": assertion,
        "scope": scopes,
        "requested_token_use": "on_behalf_of",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, data=data, timeout=30)
        if resp.status_code >= 400:
            _log.error("OBO token exchange failed: %s %s", resp.status_code, resp.text)
        resp.raise_for_status()
        body = resp.json()

    _cached_token = body["access_token"]
    _cached_expires_at = time.time() + body.get("expires_in", 3600)
    _cached_assertion = assertion
    _log.info(
        "OBO token exchange succeeded (expires in %ds)",
        int(_cached_expires_at - time.time()),
    )
    return _cached_token
