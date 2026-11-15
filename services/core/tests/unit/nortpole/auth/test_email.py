import pytest

from nortpole.auth.email_utils import build_user_email_invite, send_email
from nortpole.configs.constants import NORTPOLE_DEFAULT_APPLICATION_NAME
from nortpole.db.engine.sql_engine import SqlEngine
from nortpole.server.runtime.nortpole_runtime import NortPoleRuntime


@pytest.mark.skip(
    reason="This sends real emails, so only run when you really want to test this!"
)
def test_send_user_email_invite() -> None:
    SqlEngine.init_engine(pool_size=20, max_overflow=5)

    application_name = NORTPOLE_DEFAULT_APPLICATION_NAME

    nortpole_file = NortPoleRuntime.get_emailable_logo()

    subject = f"Invitation to Join {application_name} Organization"

    FROM_EMAIL = "noreply@nortpole.local"
    TO_EMAIL = "support@nortpole.local"
    text_content, html_content = build_user_email_invite(
        FROM_EMAIL, TO_EMAIL, NORTPOLE_DEFAULT_APPLICATION_NAME
    )

    send_email(
        TO_EMAIL,
        subject,
        html_content,
        text_content,
        mail_from=FROM_EMAIL,
        inline_png=("logo.png", nortpole_file.data),
    )
