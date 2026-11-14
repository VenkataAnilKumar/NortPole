"""Import boundaries between NortPole's own domains and the inherited platform (decision 0006).

Rules:
1. `governance` is the foundation: it imports none of `work`, `knowledge` or `insight`.
2. `insight` is the top: no other domain imports it.
3. `work` and `knowledge` may use each other and `governance`.
4. Inherited platform code reaches NortPole's domains only from the files and modules listed in `INHERITED_ENTRY_POINTS`.
   It is a ratchet: a new call from inherited code into our domains fails here until it is reviewed and listed, so the
   inherited code stays close to upstream and its dependence on our code stays visible.
"""

import ast
from pathlib import Path

CORE = Path(__file__).resolve().parents[3]
PACKAGE = CORE / "nortpole"
DOMAINS = {"governance", "work", "knowledge", "insight"}
# NortPole modules that stay at the top level (inherited code looks them up by path, or they are not a domain).
OWN_TOP_LEVEL = {"extensions", "external_permissions", "user_preferences"}

FORBIDDEN = {
    "governance": {"work", "knowledge", "insight"},
    "work": {"insight"},
    "knowledge": {"insight"},
    "insight": set(),
}

INHERITED_ENTRY_POINTS: dict[str, set[str]] = {
    "nortpole/main.py": {
        "nortpole.governance.admin_changes", "nortpole.governance.audit_log", "nortpole.governance.retention",
        "nortpole.governance.route_policy", "nortpole.governance.tool_catalog", "nortpole.insight.inventory",
        "nortpole.insight.overview", "nortpole.insight.quality", "nortpole.knowledge.knowledge_access",
        "nortpole.knowledge.source_requests", "nortpole.work.actions", "nortpole.work.packs", "nortpole.work.tasks",
        "nortpole.work.workflow_schedules",
    },
    "nortpole/access/access.py": {"nortpole.knowledge.knowledge_access"},
    "nortpole/background/celery/tasks/evolvxsi_retention/tasks.py": {"nortpole.governance.retention"},
    "nortpole/background/celery/tasks/evolvxsi_schedules/tasks.py": {"nortpole.work.workflow_schedules"},
    "nortpole/chat/execution.py": {"nortpole.governance.tool_catalog"},
    "nortpole/chat/process_message.py": {"nortpole.governance.route_policy"},
    "nortpole/connectors/edit_plan/state.py": {"nortpole.knowledge.knowledge_access"},
    "nortpole/db/connector_credential_pair.py": {"nortpole.knowledge.knowledge_access"},
    "nortpole/db/connector_edit_requests.py": {"nortpole.knowledge.knowledge_access"},
    "nortpole/llm/multi_llm.py": {"nortpole.governance.redaction", "nortpole.governance.route_policy"},
    "nortpole/server/features/build/approvals/api.py": {
        "nortpole.governance.action_binding", "nortpole.governance.route_policy",
    },
    "nortpole/tools/interface.py": {"nortpole.governance.tool_catalog"},
    "nortpole/tools/tool_constructor.py": {"nortpole.governance.tool_catalog"},
    "nortpole/tools/tool_implementations/mcp/mcp_tool.py": {"nortpole.governance.route_policy"},
}


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"), filename=str(path))):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
    return found


def _domain_modules(name: str) -> str | None:
    """`nortpole.governance.route_policy.enforce` -> `nortpole.governance.route_policy`; None for anything else."""
    parts = name.split(".")
    if len(parts) >= 3 and parts[0] == "nortpole" and parts[1] in DOMAINS:
        return ".".join(parts[:3])
    return None


def _python_files() -> list[Path]:
    return [p for p in PACKAGE.rglob("*.py") if "__pycache__" not in p.parts]


def test_domains_respect_their_layers() -> None:
    problems = []
    for path in _python_files():
        top = path.relative_to(PACKAGE).parts[0]
        if top not in DOMAINS:
            continue
        for name in _imports(path):
            target = _domain_modules(name)
            if target and target.split(".")[1] in FORBIDDEN[top]:
                problems.append(f"{path.relative_to(CORE)} ({top}) imports {name}")
    assert not problems, "Domain layer rule broken:\n" + "\n".join(sorted(problems))


def test_inherited_code_reaches_domains_only_through_listed_entry_points() -> None:
    problems = []
    seen: dict[str, set[str]] = {}
    for path in _python_files():
        top = path.relative_to(PACKAGE).parts[0]
        if top in DOMAINS or top in OWN_TOP_LEVEL:
            continue
        rel = path.relative_to(CORE).as_posix()
        targets = {t for t in (_domain_modules(n) for n in _imports(path)) if t}
        if not targets:
            continue
        seen[rel] = targets
        extra = targets - INHERITED_ENTRY_POINTS.get(rel, set())
        if extra:
            problems.append(f"{rel} newly imports {sorted(extra)}")
    assert not problems, (
        "Inherited code gained a dependency on NortPole domains. Prefer a hook in nortpole/extensions; if the call is "
        "right, add it to INHERITED_ENTRY_POINTS:\n" + "\n".join(sorted(problems))
    )
    stale = {f for f in INHERITED_ENTRY_POINTS if f not in seen}
    assert not stale, f"Entry points no longer used; remove them from the list: {sorted(stale)}"


def test_every_domain_module_lives_in_a_domain() -> None:
    for domain in DOMAINS:
        assert (PACKAGE / domain / "__init__.py").is_file(), f"{domain} is not a package"
    stray = {m for m in ("route_policy", "tasks", "packs", "quality", "knowledge_access") if (PACKAGE / m).exists()}
    assert not stray, f"Moved modules reappeared at the top level: {sorted(stray)}"
