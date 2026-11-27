from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from nortpole.chat.agent_pilots import describe_pilot
from nortpole.chat.agent_preview import agent_configuration_fingerprint
from nortpole.chat.agent_releases import validate_agent_release_dependencies
from nortpole.chat.reporting import ReportingRun
from nortpole.db.agent_preview import AgentPreview
from nortpole.db.engine.sql_engine import get_session_with_current_tenant
from nortpole.db.enums import LLMModelFlowType, Permission
from nortpole.db.llm import fetch_default_model
from nortpole.db.models import DocumentSet, DocumentSet__UserGroup, Persona, User, UserGroup, User__UserGroup
from nortpole.error_handling.exceptions import NortPoleError
from nortpole.governance.route_policy.enforce import check_route
from tests.nortpole_integration.test_tasks_flow import _up


pytestmark = pytest.mark.skipif(not _up(), reason="needs local PostgreSQL")


def test_two_reporting_runners_only_use_their_permitted_libraries() -> None:
    suffix = uuid4().hex[:8]
    with get_session_with_current_tenant() as outer:
        with Session(bind=outer.connection(), join_transaction_mode="create_savepoint") as db:
            model = fetch_default_model(db, LLMModelFlowType.CHAT)
            if model is None or model.is_router or not check_route(db, model.id).allowed:
                pytest.skip("needs a fixed default Chat model on an allowed route")
            users = [User(
                email=f"reporting-{suffix}-{role}@example.invalid",
                hashed_password="unused",
                is_active=True,
                effective_permissions=[Permission.BASIC_ACCESS.value],
            ) for role in ("finance", "support")]
            finance_user, support_user = users
            finance = DocumentSet(name=f"Finance {suffix}", is_public=False, is_up_to_date=True)
            support = DocumentSet(name=f"Support {suffix}", is_public=True, is_up_to_date=True)
            finance_group = UserGroup(name=f"Finance reporting {suffix}", is_up_to_date=True)
            db.add_all([*users, finance, support, finance_group])
            db.flush()
            db.add_all([
                User__UserGroup(user_id=finance_user.id, user_group_id=finance_group.id),
                DocumentSet__UserGroup(document_set_id=finance.id, user_group_id=finance_group.id),
            ])
            agent = Persona(
                user_id=finance_user.id, name=f"Reporting {suffix}",
                description="Reporting permission fixture", is_public=True,
            )
            db.add(agent)
            db.flush()
            configuration = AgentPreview(
                name=agent.name, system_prompt="Cite the selected sources.", pilot="reporting",
                document_set_ids=[finance.id, support.id], model_configuration_id=model.id,
            )
            fingerprint = agent_configuration_fingerprint(configuration, db)
            for user, expected in ((finance_user, {finance.name, support.name}), (support_user, {support.name})):
                info = describe_pilot(configuration, user, db)
                assert info is not None and {library.name for library in info.libraries} == expected
                allowed = validate_agent_release_dependencies(
                    configuration, fingerprint, agent, user, db, allow_partial_libraries=True,
                )
                assert set(allowed) == expected
                question = f'Reporting period: 2026-11-01 to 2026-11-07\nKnowledge sources: ["{finance.name}"]\n\nReport on budget variance.'
                if user is finance_user:
                    assert ReportingRun.from_message(question, allowed).libraries == [finance.name]
                else:
                    with pytest.raises(NortPoleError, match="unavailable for this agent"):
                        ReportingRun.from_message(question, allowed)
        outer.rollback()
