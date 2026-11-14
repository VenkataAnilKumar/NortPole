# EvolvXSI — model gateway (mock)

Today this folder holds `src/adapters/mock/mock_openai_server.py`: a small OpenAI-compatible server with deterministic
replies. Tests and the [local profile](../../infrastructure/profiles/local/README.md) use it as stand-in local and cloud
model routes, so no model or API key is needed.

Model routing, route policy, redaction and usage accounting run inside `services/core`. A separate gateway service is
planned only if routing must scale or run apart from the core (see [decision 0006](../../docs/decisions/0006-scalable-repository-structure.md)).

```bash
python src/adapters/mock/mock_openai_server.py --name local-mock --port 18001
```
