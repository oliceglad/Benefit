"""Companies, hiring needs, vacancies

Revision ID: 0001
Revises:
Create Date: 2026-10-10 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = '0001'
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('companies',
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('legal_name', sa.String(length=300), nullable=True),
    sa.Column('inn', sa.String(length=12), nullable=True),
    sa.Column('industry', sa.String(length=32), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('website', sa.String(length=300), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('size', sa.String(length=16), nullable=True),
    sa.Column('tech_stack', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('contact_name', sa.String(length=200), nullable=True),
    sa.Column('contact_email', sa.String(length=320), nullable=True),
    sa.Column('contact_phone', sa.String(length=32), nullable=True),
    sa.Column('telegram', sa.String(length=64), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_companies')),
    sa.UniqueConstraint('owner_id', name=op.f('uq_companies_owner_id'))
    )
    op.create_table('hiring_needs',
    sa.Column('company_id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('team_description', sa.Text(), nullable=False),
    sa.Column('specialization', sa.String(length=32), nullable=False),
    sa.Column('grade', sa.String(length=16), nullable=False),
    sa.Column('required_skills', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('optional_skills', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('work_formats', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('salary_from', sa.Integer(), nullable=True),
    sa.Column('salary_to', sa.Integer(), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('headcount', sa.Integer(), nullable=False),
    sa.Column('require_confirmed_grade', sa.Boolean(), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('fk_hiring_needs_company_id_companies'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_hiring_needs'))
    )
    op.create_index(op.f('ix_hiring_needs_company_id'), 'hiring_needs', ['company_id'], unique=False)
    op.create_index(op.f('ix_hiring_needs_owner_id'), 'hiring_needs', ['owner_id'], unique=False)
    op.create_table('vacancies',
    sa.Column('company_id', sa.Uuid(), nullable=False),
    sa.Column('owner_id', sa.Uuid(), nullable=False),
    sa.Column('need_id', sa.Uuid(), nullable=True),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('specialization', sa.String(length=32), nullable=False),
    sa.Column('grade', sa.String(length=16), nullable=False),
    sa.Column('skills', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=False),
    sa.Column('salary_from', sa.Integer(), nullable=True),
    sa.Column('salary_to', sa.Integer(), nullable=True),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('work_format', sa.String(length=16), nullable=True),
    sa.Column('employment_type', sa.String(length=16), nullable=True),
    sa.Column('city', sa.String(length=100), nullable=True),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['company_id'], ['companies.id'], name=op.f('fk_vacancies_company_id_companies'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['need_id'], ['hiring_needs.id'], name=op.f('fk_vacancies_need_id_hiring_needs'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_vacancies'))
    )
    op.create_index(op.f('ix_vacancies_company_id'), 'vacancies', ['company_id'], unique=False)
    op.create_index(op.f('ix_vacancies_owner_id'), 'vacancies', ['owner_id'], unique=False)
    op.create_index(op.f('ix_vacancies_specialization'), 'vacancies', ['specialization'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_vacancies_specialization'), table_name='vacancies')
    op.drop_index(op.f('ix_vacancies_owner_id'), table_name='vacancies')
    op.drop_index(op.f('ix_vacancies_company_id'), table_name='vacancies')
    op.drop_table('vacancies')
    op.drop_index(op.f('ix_hiring_needs_owner_id'), table_name='hiring_needs')
    op.drop_index(op.f('ix_hiring_needs_company_id'), table_name='hiring_needs')
    op.drop_table('hiring_needs')
    op.drop_table('companies')
