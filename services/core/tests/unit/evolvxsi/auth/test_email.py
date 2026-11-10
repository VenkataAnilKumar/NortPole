import pytest

from evolvxsi.auth.email_utils import build_user_email_invite, send_email
from evolvxsi.configs.constants import EVOLVXSI_DEFAULT_APPLICATION_NAME
from evolvxsi.db.engine.sql_engine import SqlEngine
from evolvxsi.server.runtime.evolvxsi_runtime import EvolvXSIRuntime


@pytest.mark.skip(
    reason="This sends real emails, so only run when you really want to test this!"
)
def test_send_user_email_invite() -> None:
    SqlEngine.init_engine(pool_size=20, max_overflow=5)

    application_name = EVOLVXSI_DEFAULT_APPLICATION_NAME

    evolvxsi_file = EvolvXSIRuntime.get_emailable_logo()

    subject = f"Invitation to Join {application_name} Organization"

    FROM_EMAIL = "noreply@onyx.app"
    TO_EMAIL = "support@onyx.app"
    text_content, html_content = build_user_email_invite(
        FROM_EMAIL, TO_EMAIL, EVOLVXSI_DEFAULT_APPLICATION_NAME
    )

    send_email(
        TO_EMAIL,
        subject,
        html_content,
        text_content,
        mail_from=FROM_EMAIL,
        inline_png=("logo.png", evolvxsi_file.data),
    )
