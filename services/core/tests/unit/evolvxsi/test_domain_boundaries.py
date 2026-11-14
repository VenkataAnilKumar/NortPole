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
PACKAGE = CORE / "evolvxsi"
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
    "evolvxsi/main.py": {
        "evolvxsi.governance.admin_changes", "evolvxsi.governance.audit_log", "evolvxsi.governance.retention",
        "evolvxsi.governance.route_policy", "evolvxsi.governance.tool_catalog", "evolvxsi.insight.inventory",
        "evolvxsi.insight.overview", "evolvxsi.insight.quality", "evolvxsi.knowledge.knowledge_access",
        "evolvxsi.knowledge.source_requests", "evolvxsi.work.actions", "evolvxsi.work.packs", "evolvxsi.work.tasks",
        "evolvxsi.work.workflow_schedules",
    },
    "evolvxsi/access/access.py": {"evolvxsi.knowledge.knowledge_access"},
    "evolvxsi/background/celery/tasks/evolvxsi_retention/tasks.py": {"evolvxsi.governance.retention"},
    "evolvxsi/background/celery/tasks/evolvxsi_schedules/tasks.py": {"evolvxsi.work.workflow_schedules"},
    "evolvxsi/chat/execution.py": {"evolvxsi.governance.tool_catalog"},
    "evolvxsi/chat/process_message.py": {"evolvxsi.governance.route_policy"},
    "evolvxsi/connectors/edit_plan/state.py": {"evolvxsi.knowledge.knowledge_access"},
    "evolvxsi/db/connector_credential_pair.py": {"evolvxsi.knowledge.knowledge_access"},
    "evolvxsi/db/connector_edit_requests.py": {"evolvxsi.knowledge.knowledge_access"},
    "evolvxsi/llm/multi_llm.py": {"evolvxsi.governance.redaction", "evolvxsi.governance.route_policy"},
    "evolvxsi/server/features/build/approvals/api.py": {
        "evolvxsi.governance.action_binding", "evolvxsi.governance.route_policy",
    },
    "evolvxsi/tools/interface.py": {"evolvxsi.governance.tool_catalog"},
    "evolvxsi/tools/tool_constructor.py": {"evolvxsi.governance.tool_catalog"},
    "evolvxsi/tools/tool_implementations/mcp/mcp_tool.py": {"evolvxsi.governance.route_policy"},
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
    """`evolvxsi.governance.route_policy.enforce` -> `evolvxsi.governance.route_policy`; None for anything else."""
    parts = name.split(".")
    if len(parts) >= 3 and parts[0] == "evolvxsi" and parts[1] in DOMAINS:
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
        "Inherited code gained a dependency on NortPole domains. Prefer a hook in evolvxsi/extensions; if the call is "
        "right, add it to INHERITED_ENTRY_POINTS:\n" + "\n".join(sorted(problems))
    )
    stale = {f for f in INHERITED_ENTRY_POINTS if f not in seen}
    assert not stale, f"Entry points no longer used; remove them from the list: {sorted(stale)}"


def test_every_domain_module_lives_in_a_domain() -> None:
    for domain in DOMAINS:
        assert (PACKAGE / domain / "__init__.py").is_file(), f"{domain} is not a package"
    stray = {m for m in ("route_policy", "tasks", "packs", "quality", "knowledge_access") if (PACKAGE / m).exists()}
    assert not stray, f"Moved modules reappeared at the top level: {sorted(stray)}"
