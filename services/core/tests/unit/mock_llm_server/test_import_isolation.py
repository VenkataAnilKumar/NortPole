"""The standalone provider fixture must not load the NortPole application."""

import subprocess
import sys
from pathlib import Path


def test_server_imports_no_nortpole_modules() -> None:
    backend_dir = Path(__file__).resolve().parents[3]
    code = (
        "import sys\n"
        "import tests.integration.mock_services.mock_llm_server.server\n"
        "bad = [m for m in sys.modules if m.split('.')[0] in ('nortpole', 'ee')]\n"
        "assert not bad, bad\n"
    )
    subprocess.run([sys.executable, "-c", code], cwd=backend_dir, check=True)
