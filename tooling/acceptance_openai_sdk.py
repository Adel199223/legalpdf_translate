"""Opt-in SDK metadata profile for explicitly isolated acceptance operations.

The installed SDK queries the host through Python's platform module to fill
optional diagnostic headers. On Windows that can spawn a command. Acceptance
does not need this information: report it as unknown without interrogating the
host. No ordinary client/global/default is modified.

The caller must still supply the existing key, exact endpoint and transport,
zero retries, timeout and independent approval/accounting controls. This class
neither creates authority nor bypasses a provider/body/budget restriction.
"""
from __future__ import annotations

import sys

from openai import OpenAI


class AcceptanceOpenAI(OpenAI):
    """Source-inspected SDK seam; verify with real SDK mocks after upgrades."""

    def platform_headers(self) -> dict[str, str]:
        return {
            "X-Stainless-Lang": "python",
            "X-Stainless-Package-Version": self._version,
            "X-Stainless-OS": "Unknown",
            "X-Stainless-Arch": "unknown",
            "X-Stainless-Runtime": sys.implementation.name,
            "X-Stainless-Runtime-Version": ".".join(map(str, sys.version_info[:3])),
        }
