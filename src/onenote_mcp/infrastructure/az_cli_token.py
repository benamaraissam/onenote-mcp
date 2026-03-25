"""Obtain a Microsoft Graph access token from the Azure CLI."""

import asyncio
import json
import logging
import time

_log = logging.getLogger(__name__)

_cached_token: str = ""
_cached_expires_on: float = 0.0


async def get_graph_token() -> str:
    """Return a cached Graph API token, refreshing via ``az account get-access-token`` when expired."""
    global _cached_token, _cached_expires_on  # noqa: PLW0603

    if _cached_token and time.time() < _cached_expires_on - 60:
        return _cached_token

    proc = await asyncio.create_subprocess_exec(
        "az",
        "account",
        "get-access-token",
        "--resource",
        "https://graph.microsoft.com",
        "--output",
        "json",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()

    if proc.returncode != 0:
        err = stderr.decode().strip()
        raise RuntimeError(
            f"Azure CLI failed (exit {proc.returncode}). "
            f"Run 'az login' first.\n{err}"
        )

    data = json.loads(stdout)
    _cached_token = data["accessToken"]
    _cached_expires_on = float(data.get("expiresOn", 0)) or (
        time.time() + data.get("expires_in", 3600)
    )
    _log.info("Obtained Graph token via Azure CLI (expires in %ds)", int(_cached_expires_on - time.time()))
    return _cached_token
