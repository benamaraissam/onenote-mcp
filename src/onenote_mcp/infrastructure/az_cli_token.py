"""Obtain a Microsoft Graph access token from the Azure CLI."""

import asyncio
import json
import logging
import shutil
import sys
import time

_log = logging.getLogger(__name__)

_cached_token: str = ""
_cached_expires_on: float = 0.0

# On Windows the Azure CLI is az.cmd; on Unix it is az.
_AZ_CMD = "az.cmd" if sys.platform == "win32" else "az"


def _resolve_az() -> str:
    """Return the az executable name, raising a clear error if not on PATH."""
    cmd = _AZ_CMD
    if shutil.which(cmd) is None:
        # Fallback: try the other variant (e.g. bare 'az' on Windows with some installs)
        alt = "az" if cmd == "az.cmd" else "az.cmd"
        if shutil.which(alt) is not None:
            return alt
        raise RuntimeError(
            "Azure CLI not found. Install it from https://aka.ms/installazurecli "
            "and run 'az login'."
        )
    return cmd


async def get_graph_token() -> str:
    """Return a cached Graph API token, refreshing via ``az account get-access-token`` when expired."""
    global _cached_token, _cached_expires_on  # noqa: PLW0603

    if _cached_token and time.time() < _cached_expires_on - 60:
        return _cached_token

    az = _resolve_az()
    proc = await asyncio.create_subprocess_exec(
        az,
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
