"""Matching by vacancy: settings, version, feedback and stored snapshot

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-11 00:03:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('vacancies', sa.Column('matching_settings', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))
    op.add_column('vacancies', sa.Column('matching_version', sa.Integer(), server_default='1', nullable=False))

    op.alter_column('need_feedback', 'need_id', existing_type=sa.Uuid(), nullable=True)
    op.add_column('need_feedback', sa.Column('vacancy_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_need_feedback_vacancy_id'), 'need_feedback', ['vacancy_id'], unique=False)
    op.create_foreign_key(op.f('fk_need_feedback_vacancy_id_vacancies'), 'need_feedback', 'vacancies', ['vacancy_id'], ['id'], ondelete='CASCADE')
    op.create_unique_constraint(op.f('uq_need_feedback_vacancy_id'), 'need_feedback', ['vacancy_id', 'candidate_id'])
    op.create_check_constraint(op.f('ck_need_feedback_one_target'), 'need_feedback', 'num_nonnulls(need_id, vacancy_id) = 1')

    op.create_table('vacancy_match_snapshots',
    sa.Column('vacancy_id', sa.Uuid(), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('criteria_hash', sa.String(length=64), nullable=False),
    sa.Column('feedback_hash', sa.String(length=64), nullable=False),
    sa.Column('reason', sa.String(length=16), nullable=False),
    sa.Column('computed_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.ForeignKeyConstraint(['vacancy_id'], ['vacancies.id'], name=op.f('fk_vacancy_match_snapshots_vacancy_id_vacancies'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('vacancy_id', name=op.f('pk_vacancy_match_snapshots'))
    )

    # Вакансии, созданные из потребности: её настройки подбора и отметки
    # переходят к вакансии (дальше вакансия живёт своими критериями).
    op.execute("""
        UPDATE vacancies v SET matching_settings = jsonb_build_object(
            'require_confirmed_grade', n.require_confirmed_grade,
            'strict_skills', n.strict_skills,
            'grade_tolerance', n.grade_tolerance,
            'min_experience_months', n.min_experience_months,
            'hard_budget', n.hard_budget,
            'strict_format', n.strict_format
        )
        FROM hiring_needs n WHERE v.need_id = n.id
    """)
    op.execute("""
        INSERT INTO need_feedback (id, vacancy_id, candidate_id, verdict, comment, created_at, updated_at)
        SELECT gen_random_uuid(), v.id, f.candidate_id, f.verdict, f.comment, f.created_at, f.updated_at
        FROM vacancies v JOIN need_feedback f ON f.need_id = v.need_id
    """)


def downgrade() -> None:
    op.drop_table('vacancy_match_snapshots')
    op.execute("DELETE FROM need_feedback WHERE vacancy_id IS NOT NULL")
    op.drop_constraint(op.f('ck_need_feedback_one_target'), 'need_feedback', type_='check')
    op.drop_constraint(op.f('uq_need_feedback_vacancy_id'), 'need_feedback', type_='unique')
    op.drop_constraint(op.f('fk_need_feedback_vacancy_id_vacancies'), 'need_feedback', type_='foreignkey')
    op.drop_index(op.f('ix_need_feedback_vacancy_id'), table_name='need_feedback')
    op.drop_column('need_feedback', 'vacancy_id')
    op.alter_column('need_feedback', 'need_id', existing_type=sa.Uuid(), nullable=False)
    op.drop_column('vacancies', 'matching_version')
    op.drop_column('vacancies', 'matching_settings')
