"""Initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_number", sa.Integer(), sa.Identity(start=1), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("hashed_password", sa.String(128), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("is_email_verified", sa.Boolean(), nullable=False),
        sa.Column("email_verification_token", sa.String(64), nullable=True),
        sa.Column("password_reset_token", sa.String(64), nullable=True),
        sa.Column("password_reset_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_number", name="uq_users_user_number"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_agent", sa.String(512), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=False),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("replaced_by", sa.Uuid(), nullable=True),
        sa.Column("revoked", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_refresh_tokens_token_hash"),
    )
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"])

    op.create_table(
        "credit_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("balance", sa.Numeric(18, 4), nullable=False),
        sa.Column("max_cpu_quota", sa.Numeric(6, 2), nullable=False),
        sa.Column("max_memory_mb_quota", sa.Integer(), nullable=False),
        sa.Column("max_storage_gb_quota", sa.Integer(), nullable=False),
        sa.Column("max_deployments_quota", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("balance >= 0", name="ck_credit_accounts_balance_non_negative"),
    )
    op.create_index("ix_credit_accounts_user_id", "credit_accounts", ["user_id"], unique=True)

    op.create_table(
        "credit_transactions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("account_id", sa.Uuid(), sa.ForeignKey("credit_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("balance_after", sa.Numeric(18, 4), nullable=False),
        sa.Column("deployment_id", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("idempotency_key", name="uq_credit_transactions_idempotency_key"),
    )
    op.create_index("ix_credit_transactions_account_id", "credit_transactions", ["account_id"])
    op.create_index("ix_credit_transactions_deployment_id", "credit_transactions", ["deployment_id"])
    op.create_index("ix_credit_transactions_created_at", "credit_transactions", ["created_at"])

    op.create_table(
        "pricing_plans",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("base_cost_per_hour", sa.Numeric(18, 4), nullable=False),
        sa.Column("cpu_cost_per_core_hour", sa.Numeric(18, 4), nullable=False),
        sa.Column("memory_cost_per_gb_hour", sa.Numeric(18, 4), nullable=False),
        sa.Column("storage_cost_per_gb_hour", sa.Numeric(18, 4), nullable=False),
        sa.Column("service_cost_per_hour", sa.Numeric(18, 4), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_pricing_plans_name"),
    )
    op.create_index("ix_pricing_plans_is_active", "pricing_plans", ["is_active"])

    op.create_table(
        "images",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("pattern", sa.String(256), nullable=False),
        sa.Column("mode", sa.String(8), nullable=False),
        sa.Column("reason", sa.String(256), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("pattern", name="uq_images_pattern"),
    )

    op.create_table(
        "compose_templates",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("submitted_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("compose_yaml", sa.Text(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_compose_templates_submitted_by", "compose_templates", ["submitted_by"])
    op.create_index("ix_compose_templates_status", "compose_templates", ["status"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(32), nullable=False),
        sa.Column("resource_id", sa.String(64), nullable=False),
        sa.Column("ip_address", sa.String(64), nullable=False),
        sa.Column("detail", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "host_metrics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("cpu_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("memory_used_mb", sa.Integer(), nullable=False),
        sa.Column("memory_total_mb", sa.Integer(), nullable=False),
        sa.Column("disk_used_gb", sa.Numeric(10, 2), nullable=False),
        sa.Column("disk_total_gb", sa.Numeric(10, 2), nullable=False),
        sa.Column("running_containers", sa.Integer(), nullable=False),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_host_metrics_sampled_at", "host_metrics", ["sampled_at"])

    op.create_table(
        "deployments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("node_id", sa.String(64), nullable=False),
        sa.Column("cpu_cores", sa.Numeric(6, 2), nullable=False),
        sa.Column("memory_mb", sa.Integer(), nullable=False),
        sa.Column("storage_gb", sa.Integer(), nullable=False),
        sa.Column("spec", JSONB(), nullable=False),
        sa.Column("price_snapshot", JSONB(), nullable=False),
        sa.Column("estimated_hourly_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("public_url", sa.String(256), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("template_id", sa.Uuid(), sa.ForeignKey("compose_templates.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deployments_owner_id", "deployments", ["owner_id"])
    op.create_index("ix_deployments_slug", "deployments", ["slug"], unique=True)
    op.create_index("ix_deployments_status", "deployments", ["status"])

    op.create_table(
        "deployment_services",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("deployment_id", sa.Uuid(), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_name", sa.String(64), nullable=False),
        sa.Column("image", sa.String(256), nullable=False),
        sa.Column("container_id", sa.String(128), nullable=True),
        sa.Column("container_name", sa.String(128), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("restart_count", sa.Integer(), nullable=False),
        sa.Column("is_web", sa.Boolean(), nullable=False),
        sa.Column("internal_port", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deployment_services_deployment_id", "deployment_services", ["deployment_id"])

    op.create_table(
        "deployment_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("deployment_id", sa.Uuid(), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("dispatched", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deployment_events_deployment_id", "deployment_events", ["deployment_id"])
    op.create_index("ix_deployment_events_event_type", "deployment_events", ["event_type"])
    op.create_index("ix_deployment_events_dispatched", "deployment_events", ["dispatched"])
    op.create_index("ix_deployment_events_created_at", "deployment_events", ["created_at"])

    op.create_table(
        "deployment_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("deployment_id", sa.Uuid(), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("level", sa.String(16), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_deployment_logs_deployment_id", "deployment_logs", ["deployment_id"])
    op.create_index("ix_deployment_logs_created_at", "deployment_logs", ["created_at"])

    op.create_table(
        "usage_records",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("deployment_id", sa.Uuid(), sa.ForeignKey("deployments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("credits_charged", sa.Numeric(18, 4), nullable=False),
        sa.Column("price_snapshot", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("deployment_id", "period_start", name="uq_usage_period"),
    )
    op.create_index("ix_usage_records_deployment_id", "usage_records", ["deployment_id"])


def downgrade() -> None:
    for table in (
        "usage_records",
        "deployment_logs",
        "deployment_events",
        "deployment_services",
        "deployments",
        "host_metrics",
        "audit_logs",
        "compose_templates",
        "images",
        "pricing_plans",
        "credit_transactions",
        "credit_accounts",
        "refresh_tokens",
        "sessions",
        "users",
    ):
        op.drop_table(table)
