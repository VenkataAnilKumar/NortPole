"""The images bake the default model at its pinned revision: the model-server image
its weights, the API image its tokenizer. The API image also bakes the nomic
tokenizer for chat token counting."""

import re
from pathlib import Path

from shared_configs.configs import DEFAULT_DOCUMENT_ENCODER_MODEL
from shared_configs.embedding_models import get_local_model_spec

_BACKEND_DIR = Path(__file__).resolve().parents[3]
_NOMIC = "nomic-ai/nomic-embed-text-v1"
_TOKENIZER_BAKE_PATTERN = re.compile(
    r"Tokenizer\.from_pretrained\('(?P<name>[^']+)'"
    r"(?:,\s*revision='(?P<revision>[^']+)')?\)"
)


def _default_model_revision() -> str:
    spec = get_local_model_spec(DEFAULT_DOCUMENT_ENCODER_MODEL)
    assert spec is not None and spec.hf_revision is not None
    return spec.hf_revision


# EvolvXSI does not build or deploy a model-server image (upstream's Dockerfile.model_server is not part of this
# repository), so only the API image is checked here.


def test_api_image_bakes_the_tokenizers_it_loads() -> None:
    text = (_BACKEND_DIR / "Dockerfile").read_text()

    baked = {
        match.group("name"): match.group("revision")
        for match in _TOKENIZER_BAKE_PATTERN.finditer(text)
    }
    # The default tokenizer (chat token counting, the fallback) must work offline.
    # It loads without a revision, so the bake has none.
    assert _NOMIC in baked and baked[_NOMIC] is None
    # The API server loads registry tokenizers at their pinned revision.
    assert baked.get(DEFAULT_DOCUMENT_ENCODER_MODEL) == _default_model_revision()
    for model_name, revision in baked.items():
        spec = get_local_model_spec(model_name)
        assert spec is None or revision == spec.hf_revision, model_name
