"""Record indexed Knowledge changes for opt-in workflow triggers."""

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "ca2c7423ab98"
down_revision = "a1911b5ce936"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("nortpole_task", sa.Column("knowledge_trigger", JSONB()))
    op.add_column("nortpole_workflow_schedule", sa.Column("source_library_id", sa.Integer()))
    op.add_column("nortpole_workflow_schedule", sa.Column("source_since", sa.DateTime(timezone=True)))
    op.add_column("nortpole_workflow_schedule", sa.Column("source_scan_at", sa.DateTime(timezone=True)))
    op.create_index(
        "ix_workflow_schedule_sources", "nortpole_workflow_schedule", ["source_scan_at", "id"],
        postgresql_where=sa.text("cadence = 'source' AND state = 'active'"),
    )
    op.add_column("nortpole_workflow_run", sa.Column("source_event_id", sa.BigInteger()))
    op.add_column("nortpole_workflow_run", sa.Column("source_library_id", sa.Integer()))
    op.add_column("nortpole_workflow_run", sa.Column("source_document_id", sa.Text()))
    op.add_column("nortpole_workflow_run", sa.Column("source_content_hash", sa.String()))
    op.create_unique_constraint(
        "uq_workflow_run_source_event", "nortpole_workflow_run", ["schedule_id", "source_event_id"],
    )
    op.create_index(
        "ix_workflow_run_source_queued", "nortpole_workflow_run", ["fired_at"],
        postgresql_where=sa.text("outcome = 'queued' AND trigger = 'source'"),
    )
    op.create_table(
        "nortpole_knowledge_change",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("document_id", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.clock_timestamp(), nullable=False),
    )
    op.create_index("ix_knowledge_change_time", "nortpole_knowledge_change", ["created_at"])
    op.create_index("ix_knowledge_change_document", "nortpole_knowledge_change", ["document_id", "id"])
    op.execute("""
        CREATE FUNCTION nortpole_record_knowledge_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        DECLARE watches_knowledge boolean;
        BEGIN
            IF NEW.content_hash IS NULL THEN
                RETURN NEW;
            END IF;
            IF TG_OP = 'UPDATE' AND NEW.content_hash IS NOT DISTINCT FROM OLD.content_hash THEN
                RETURN NEW;
            END IF;
            EXECUTE format(
                'SELECT EXISTS (SELECT 1 FROM %I.nortpole_workflow_schedule
                 WHERE cadence = ''source'' AND state = ''active'')', TG_TABLE_SCHEMA
            ) INTO watches_knowledge;
            IF watches_knowledge THEN
                EXECUTE format(
                    'INSERT INTO %I.nortpole_knowledge_change (document_id, content_hash) VALUES ($1, $2)',
                    TG_TABLE_SCHEMA
                ) USING NEW.id, NEW.content_hash;
            END IF;
            RETURN NEW;
        END $$;
    """)
    op.execute("""
        CREATE TRIGGER nortpole_knowledge_content_changed
        AFTER INSERT OR UPDATE OF content_hash ON document
        FOR EACH ROW EXECUTE FUNCTION nortpole_record_knowledge_change();
    """)


def downgrade() -> None:
    op.drop_column("nortpole_task", "knowledge_trigger")
    op.execute("DROP TRIGGER nortpole_knowledge_content_changed ON document")
    op.execute("DROP FUNCTION nortpole_record_knowledge_change()")
    op.drop_table("nortpole_knowledge_change")
    op.drop_index("ix_workflow_run_source_queued", table_name="nortpole_workflow_run")
    op.drop_constraint("uq_workflow_run_source_event", "nortpole_workflow_run", type_="unique")
    for name in ("source_event_id", "source_library_id", "source_document_id", "source_content_hash"):
        op.drop_column("nortpole_workflow_run", name)
    op.drop_index("ix_workflow_schedule_sources", table_name="nortpole_workflow_schedule")
    for name in ("source_scan_at", "source_since", "source_library_id"):
        op.drop_column("nortpole_workflow_schedule", name)
