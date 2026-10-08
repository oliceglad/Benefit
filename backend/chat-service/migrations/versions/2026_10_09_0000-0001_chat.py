"""Conversations, messages, attachments, tasks, outbox

Revision ID: 0001
Revises:
Create Date: 2026-10-09 00:00:00
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
    op.create_table('conversations',
    sa.Column('invitation_id', sa.Uuid(), nullable=False),
    sa.Column('candidate_id', sa.Uuid(), nullable=False),
    sa.Column('employer_id', sa.Uuid(), nullable=False),
    sa.Column('vacancy_title', sa.String(length=200), nullable=False),
    sa.Column('company_name', sa.String(length=200), nullable=False),
    sa.Column('invitation_status', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('last_message_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('candidate_last_read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('employer_last_read_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_conversations')),
    sa.UniqueConstraint('invitation_id', name=op.f('uq_conversations_invitation_id'))
    )
    op.create_index(op.f('ix_conversations_candidate_id'), 'conversations', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_conversations_employer_id'), 'conversations', ['employer_id'], unique=False)
    op.create_table('outbox_messages',
    sa.Column('id', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('kind', sa.String(length=64), nullable=False),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('attempts', sa.Integer(), server_default='0', nullable=False),
    sa.Column('next_attempt_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('failed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_outbox_messages'))
    )
    op.create_table('tasks',
    sa.Column('conversation_id', sa.Uuid(), nullable=False),
    sa.Column('employer_id', sa.Uuid(), nullable=False),
    sa.Column('candidate_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('description', sa.Text(), nullable=False),
    sa.Column('due_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('response_type', sa.String(length=16), nullable=True),
    sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('submission_message_id', sa.Uuid(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('score', sa.Integer(), nullable=True),
    sa.Column('feedback', sa.Text(), nullable=True),
    sa.Column('reminded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('recurrence_days', sa.Integer(), nullable=True),
    sa.Column('next_issue_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('series_id', sa.Uuid(), nullable=True),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name=op.f('fk_tasks_conversation_id_conversations'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tasks'))
    )
    op.create_index(op.f('ix_tasks_candidate_id'), 'tasks', ['candidate_id'], unique=False)
    op.create_index(op.f('ix_tasks_conversation_id'), 'tasks', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_tasks_employer_id'), 'tasks', ['employer_id'], unique=False)
    op.create_table('messages',
    sa.Column('conversation_id', sa.Uuid(), nullable=False),
    sa.Column('sender_id', sa.Uuid(), nullable=True),
    sa.Column('kind', sa.String(length=16), nullable=False),
    sa.Column('text', sa.Text(), nullable=False),
    sa.Column('task_id', sa.Uuid(), nullable=True),
    sa.Column('client_id', sa.String(length=64), nullable=True),
    sa.Column('seq', sa.BigInteger(), sa.Identity(always=False), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name=op.f('fk_messages_conversation_id_conversations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['task_id'], ['tasks.id'], name=op.f('fk_messages_task_id_tasks'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_messages')),
    sa.UniqueConstraint('conversation_id', 'client_id', name=op.f('uq_messages_conversation_id')),
    sa.UniqueConstraint('seq', name=op.f('uq_messages_seq'))
    )
    op.create_index('ix_messages_conversation_created', 'messages', ['conversation_id', 'created_at'], unique=False)
    op.create_table('attachments',
    sa.Column('conversation_id', sa.Uuid(), nullable=False),
    sa.Column('uploader_id', sa.Uuid(), nullable=False),
    sa.Column('message_id', sa.Uuid(), nullable=True),
    sa.Column('filename', sa.String(length=255), nullable=False),
    sa.Column('content_type', sa.String(length=100), nullable=False),
    sa.Column('size', sa.Integer(), nullable=False),
    sa.Column('storage_key', sa.String(length=100), nullable=False),
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['conversation_id'], ['conversations.id'], name=op.f('fk_attachments_conversation_id_conversations'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['message_id'], ['messages.id'], name=op.f('fk_attachments_message_id_messages'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_attachments')),
    sa.UniqueConstraint('storage_key', name=op.f('uq_attachments_storage_key'))
    )
    op.create_index(op.f('ix_attachments_conversation_id'), 'attachments', ['conversation_id'], unique=False)
    op.create_index(op.f('ix_attachments_message_id'), 'attachments', ['message_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_attachments_message_id'), table_name='attachments')
    op.drop_index(op.f('ix_attachments_conversation_id'), table_name='attachments')
    op.drop_table('attachments')
    op.drop_index('ix_messages_conversation_created', table_name='messages')
    op.drop_table('messages')
    op.drop_index(op.f('ix_tasks_employer_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_conversation_id'), table_name='tasks')
    op.drop_index(op.f('ix_tasks_candidate_id'), table_name='tasks')
    op.drop_table('tasks')
    op.drop_table('outbox_messages')
    op.drop_index(op.f('ix_conversations_employer_id'), table_name='conversations')
    op.drop_index(op.f('ix_conversations_candidate_id'), table_name='conversations')
    op.drop_table('conversations')
