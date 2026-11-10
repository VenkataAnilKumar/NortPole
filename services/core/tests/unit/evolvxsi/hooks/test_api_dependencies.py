"""Unit tests for the hooks feature gate."""

from unittest.mock import patch

import pytest

from evolvxsi.error_handling.error_codes import EvolvXSIErrorCode
from evolvxsi.error_handling.exceptions import EvolvXSIError
from evolvxsi.hooks.api_dependencies import require_hook_enabled


class TestRequireHookEnabled:
    def test_raises_when_multi_tenant(self) -> None:
        with patch("evolvxsi.hooks.api_dependencies.MULTI_TENANT", True):
            with pytest.raises(EvolvXSIError) as exc_info:
                require_hook_enabled()
        assert exc_info.value.error_code is EvolvXSIErrorCode.SINGLE_TENANT_ONLY
        assert exc_info.value.status_code == 403
        assert "multi-tenant" in exc_info.value.detail

    def test_passes_when_single_tenant(self) -> None:
        with patch("evolvxsi.hooks.api_dependencies.MULTI_TENANT", False):
            require_hook_enabled()  # must not raise
