"""The microVM router is mounted only with `SANDBOX_RUNTIME=firecracker`."""

import importlib

import pytest
from fastapi.routing import APIRoute

from nortpole.server.features.build.configs import SandboxRuntime
from nortpole.server.features.microvm.api import SANDBOX_NODE_SIGNING_KEY_PATH


def _has_signing_key_route(runtime: SandboxRuntime) -> bool:
    nortpole_main = importlib.import_module("nortpole.main")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(nortpole_main, "SANDBOX_RUNTIME", runtime)
        mp.setattr(nortpole_main, "APP_API_PREFIX", "")
        app = nortpole_main.get_application()
    return any(
        isinstance(route, APIRoute)
        and route.path == SANDBOX_NODE_SIGNING_KEY_PATH
        and "PUT" in route.methods
        for route in app.routes
    )


def test_signing_key_route_path() -> None:
    assert SANDBOX_NODE_SIGNING_KEY_PATH == "/microvm/node/signing-key"


def test_signing_key_route_absent_with_pod_runtime() -> None:
    assert not _has_signing_key_route(SandboxRuntime.POD)


def test_signing_key_route_present_with_firecracker_runtime() -> None:
    assert _has_signing_key_route(SandboxRuntime.FIRECRACKER)
