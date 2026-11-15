"""Point search at an OpenAI-compatible embedding server (for example Ollama with
nomic-embed-text). Run inside the API container, then restart the API so it creates
the matching index:

  docker compose exec api python scripts/setup_local_embeddings.py \
      --api http://127.0.0.1:8080 --email ADMIN --password PASS \
      --url http://host.docker.internal:11434/v1 --model nomic-embed-text --dim 768

Two things are done directly in the database because the admin API has no call for them:
the active search settings row is rewritten (model, dimension, a new index name), and
the prefixes are emptied (OpenAI-compatible providers reject them). Any pending
(FUTURE) row is deleted. Sandbox-checked; changing the embedding model of a workspace
that already has indexed documents needs a re-index this script does not do.
"""

import argparse
import re
import sys
from pathlib import Path

import requests
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from nortpole.db.engine.sql_engine import SqlEngine, get_session_with_current_tenant  # noqa: E402


def main() -> None:
    a = argparse.ArgumentParser()
    a.add_argument("--api", default="http://127.0.0.1:8080")
    a.add_argument("--email", required=True)
    a.add_argument("--password", required=True)
    a.add_argument("--url", required=True)
    a.add_argument("--model", default="nomic-embed-text")
    a.add_argument("--dim", type=int, default=768)
    a.add_argument("--key", default="not-needed")
    args = a.parse_args()

    s = requests.Session()
    r = s.post(f"{args.api}/auth/login", data={"username": args.email, "password": args.password}, timeout=30)
    if r.status_code not in (200, 204):
        sys.exit(f"sign-in failed ({r.status_code})")
    r = s.put(f"{args.api}/admin/embedding/embedding-provider",
              json={"provider_type": "openai_compatible", "api_url": args.url, "api_key": args.key}, timeout=60)
    if r.status_code != 200:
        sys.exit(f"embedding provider was not saved ({r.status_code}): {r.text[:200]}")

    index = "nortpole_chunk_" + re.sub(r"[^a-z0-9]+", "_", args.model.lower()).strip("_")
    SqlEngine.init_engine(pool_size=2, max_overflow=0)
    with get_session_with_current_tenant() as db:
        db.execute(text("delete from search_settings where status = 'FUTURE'"))
        n = db.execute(text(
            "update search_settings set model_name=:m, model_dim=:d, provider_type='OPENAI_COMPATIBLE', index_name=:i, "
            "vector_quantization='NONE', query_prefix='', passage_prefix='' where status = 'PRESENT'"),
            {"m": args.model, "d": args.dim, "i": index}).rowcount
        db.commit()
    print(f"embedding provider saved; {n} active search settings row set to {args.model} ({args.dim}) with index {index}. Restart the API now.")


if __name__ == "__main__":
    main()
