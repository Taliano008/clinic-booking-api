"""initial schema: doctors, working_hours, patients, appointments

Revision ID: 0001
Revises:
Create Date: 2026-10-16
"""

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "doctors",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("specialty", sa.String(120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )

    op.create_table(
        "patients",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(32), nullable=True),
        sa.UniqueConstraint("email", name="uq_patients_email"),
    )

    op.create_table(
        "working_hours",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "doctor_id",
            sa.Integer(),
            sa.ForeignKey(
                "doctors.id", ondelete="CASCADE", name="fk_working_hours_doctor_id_doctors"
            ),
            nullable=False,
        ),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.CheckConstraint("weekday BETWEEN 0 AND 6", name="ck_working_hours_weekday_range"),
        sa.CheckConstraint("end_time > start_time", name="ck_working_hours_end_after_start"),
        sa.UniqueConstraint(
            "doctor_id", "weekday", "start_time", name="uq_working_hours_doctor_id"
        ),
    )

    op.create_table(
        "appointments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "doctor_id",
            sa.Integer(),
            sa.ForeignKey("doctors.id", name="fk_appointments_doctor_id_doctors"),
            nullable=False,
        ),
        sa.Column(
            "patient_id",
            sa.Integer(),
            sa.ForeignKey("patients.id", name="fk_appointments_patient_id_patients"),
            nullable=False,
        ),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="booked"),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "status IN ('booked', 'cancelled')", name="ck_appointments_status_valid"
        ),
        sa.CheckConstraint("end_time > start_time", name="ck_appointments_end_after_start"),
        sa.CheckConstraint(
            "status <> 'cancelled' OR cancel_reason IS NOT NULL",
            name="ck_appointments_cancel_has_reason",
        ),
    )

    # The core invariant: one ACTIVE appointment per doctor per start time.
    op.create_index(
        "uq_appointments_active_slot",
        "appointments",
        ["doctor_id", "start_time"],
        unique=True,
        postgresql_where=sa.text("status = 'booked'"),
        sqlite_where=sa.text("status = 'booked'"),
    )
    op.create_index("ix_appointments_patient_start", "appointments", ["patient_id", "start_time"])


def downgrade() -> None:
    op.drop_index("ix_appointments_patient_start", table_name="appointments")
    op.drop_index("uq_appointments_active_slot", table_name="appointments")
    op.drop_table("appointments")
    op.drop_table("working_hours")
    op.drop_table("patients")
    op.drop_table("doctors")
