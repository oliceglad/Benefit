"""Vacancy model: required/optional skills, responsibilities, salary tax mode, archive

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-11 00:02:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '0004'
down_revision: str | None = '0003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _json_list(name: str) -> sa.Column:
    return sa.Column(name, postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False)


def upgrade() -> None:
    op.add_column('vacancies', _json_list('required_skills'))
    op.add_column('vacancies', _json_list('optional_skills'))
    op.add_column('vacancies', _json_list('responsibilities'))
    op.add_column('vacancies', sa.Column('salary_type', sa.String(length=8), server_default='gross', nullable=False))
    op.add_column('vacancies', sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('vacancies', sa.Column('archived_at', sa.DateTime(timezone=True), nullable=True))
    # Прежние навыки вакансии считаем обязательными.
    op.execute("UPDATE vacancies SET required_skills = skills")
    op.execute("UPDATE vacancies SET closed_at = updated_at WHERE status = 'closed'")
    op.drop_column('vacancies', 'skills')


def downgrade() -> None:
    op.add_column('vacancies', _json_list('skills'))
    op.execute("UPDATE vacancies SET skills = required_skills || optional_skills")
    op.execute("UPDATE vacancies SET status = 'closed' WHERE status = 'archived'")
    for column in ('archived_at', 'closed_at', 'salary_type', 'responsibilities', 'optional_skills', 'required_skills'):
        op.drop_column('vacancies', column)
