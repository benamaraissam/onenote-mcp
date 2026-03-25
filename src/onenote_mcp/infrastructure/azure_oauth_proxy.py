"""OAuthProxy variant compatible with Microsoft Entra ID v2 authorize URL."""

from __future__ import annotations

from typing import Any

from fastmcp.server.auth import OAuthProxy

# Azure v2 requires openid + offline_access alongside any custom API scope so it
# returns an ID token and refresh token during the authorization code exchange.
_AZURE_REQUIRED_OIDC_SCOPES = ["openid", "offline_access"]


class AzureOAuthProxy(OAuthProxy):
    """OAuthProxy adapted for Microsoft Entra ID v2.

    Three Entra-specific quirks are handled here:

    1. ``resource`` parameter — MCP clients attach ``resource=<MCP base URL>/mcp``
       (RFC 8707). Entra v2 rejects it with AADSTS9010010 when it conflicts with the
       ``scope`` value.  We strip it before forwarding to Azure.

    2. ``openid`` / ``offline_access`` — Entra v2 requires these OIDC scopes alongside
       any custom API scope to issue ID tokens and refresh tokens.  We inject them
       automatically so the caller does not have to list them in ``extra_authorize_params``.

    3. ``required_scopes`` / ``_default_scope_str`` — ``OAuthProxy.__init__`` computes
       ``_default_scope_str`` from ``self.required_scopes`` *before* the caller can set
       ``valid_scopes``.  If a DCR client registers without an explicit scope the SDK
       assigns ``_default_scope_str`` (which would be ``""``), and the subsequent
       ``validate_scope`` call raises ``InvalidScopeError`` before ``provider.authorize``
       is ever reached.  We fix this by patching both attributes post-construction.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        # Pull out valid_scopes before forwarding to parent so we can use it
        # to patch required_scopes / _default_scope_str after super().__init__.
        valid_scopes: list[str] | None = kwargs.get("valid_scopes")
        super().__init__(*args, **kwargs)
        if valid_scopes:
            # _default_scope_str: used as fallback scope when a DCR client registers
            # without an explicit scope — must be the full URI so validate_scope passes.
            self._default_scope_str = " ".join(valid_scopes)

            # required_scopes: checked by the bearer-auth middleware against the
            # upstream token's `scp` claim.  Azure v2 puts the *short* scope name in
            # `scp` (e.g. "mcp-access"), NOT the full "api://<app-id>/mcp-access" URI.
            # Using the full URI here would always produce 403 insufficient_scope.
            self.required_scopes = [s.rsplit("/", 1)[-1] for s in valid_scopes]

    async def authorize(self, client: Any, params: Any) -> str:  # type: ignore[override]
        import sys
        print(f"\n>>> AzureOAuthProxy.authorize called, client={getattr(client,'client_id',None)}", file=sys.stderr, flush=True)
        url = await super().authorize(client, params)
        print(f"\n>>> AUTHORIZE REDIRECT URL:\n{url}\n", file=sys.stderr, flush=True)
        return url

    def _build_upstream_authorize_url(self, txn_id: str, transaction: dict[str, Any]) -> str:
        tx = dict(transaction)
        tx.pop("resource", None)

        # Ensure openid + offline_access are included alongside the custom API scope.
        scopes: list[str] = list(tx.get("scopes") or [])
        for s in _AZURE_REQUIRED_OIDC_SCOPES:
            if s not in scopes:
                scopes.append(s)
        tx["scopes"] = scopes

        url = super()._build_upstream_authorize_url(txn_id, tx)
        import sys
        print(f"\n>>> AZURE UPSTREAM AUTHORIZE URL:\n{url}\n", file=sys.stderr, flush=True)
        return url

    def _prepare_scopes_for_token_exchange(self, scopes: list[str]) -> list[str]:
        """Include openid/offline_access during the authorization-code → token exchange.

        Azure (AADSTS28003) requires scopes at the token endpoint.  Entra also needs
        openid/offline_access to issue an ID token and refresh token.
        """
        result = list(scopes)
        for s in _AZURE_REQUIRED_OIDC_SCOPES:
            if s not in result:
                result.append(s)
        return result
