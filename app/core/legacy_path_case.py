from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send


class LegacyPathCaseCompatibilityMiddleware:
    """Maps legacy-case route prefixes to canonical lowercase API routes."""

    _prefix_map: tuple[tuple[str, str], ...] = (
        ("/api/Auth", "/api/auth"),
        ("/api/Quote", "/api/quote"),
    )

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") == "http":
            path = scope.get("path") or ""
            for legacy_prefix, canonical_prefix in self._prefix_map:
                if path == legacy_prefix or path.startswith(f"{legacy_prefix}/"):
                    rewritten_path = f"{canonical_prefix}{path[len(legacy_prefix):]}"
                    rewritten_scope = dict(scope)
                    rewritten_scope["path"] = rewritten_path
                    if "raw_path" in rewritten_scope:
                        rewritten_scope["raw_path"] = rewritten_path.encode("utf-8")
                    await self.app(rewritten_scope, receive, send)
                    return

        await self.app(scope, receive, send)
