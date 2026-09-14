"""add google oauth fields to users

Revision ID: 70c55e969973
Revises: 06316e98fd73
Create Date: 2026-09-13 16:22:29.547809

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '70c55e969973'
down_revision: Union[str, None] = '06316e98fd73'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Unlike every prior migration's enum columns (created together with their
    # table via op.create_table, which auto-creates the Postgres type), this
    # adds an enum column to an EXISTING table -- the type must be created
    # explicitly first, or ADD COLUMN fails with "type does not exist".
    auth_provider_enum = sa.Enum('LOCAL', 'GOOGLE', name='auth_provider')
    auth_provider_enum.create(op.get_bind(), checkfirst=True)

    # Existing rows (every user seeded/created before this phase) must get a
    # concrete value -- LOCAL is correct for all of them, since Google auth
    # didn't exist yet. server_default is dropped right after backfilling so
    # the column definition matches the model (no implicit default at the DB
    # level; app/models/user.py's default=AuthProvider.LOCAL handles new rows).
    op.add_column(
        'users',
        sa.Column('auth_provider', auth_provider_enum, nullable=False, server_default='LOCAL'),
    )
    op.alter_column('users', 'auth_provider', server_default=None)
    op.add_column('users', sa.Column('google_id', sa.String(length=255), nullable=True))
    op.alter_column('users', 'password_hash',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
    op.create_index(op.f('ix_users_google_id'), 'users', ['google_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_users_google_id'), table_name='users')
    op.alter_column('users', 'password_hash',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.drop_column('users', 'google_id')
    op.drop_column('users', 'auth_provider')
    sa.Enum(name='auth_provider').drop(op.get_bind(), checkfirst=True)
