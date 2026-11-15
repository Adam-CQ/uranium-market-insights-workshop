"""Create provenance foundations. Frozen schema; later changes use new revisions."""
from alembic import op
import sqlalchemy as sa

revision = "0001_provenance"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('data_source',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.Text(), nullable=False),
    sa.Column('url', sa.Text(), nullable=False),
    sa.Column('cadence', sa.Text(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('name')
    )
    op.create_table('ingestion_run',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('source_url', sa.Text(), nullable=False),
    sa.Column('source_table', sa.Text(), nullable=False),
    sa.Column('source_vintage', sa.Text(), nullable=False),
    sa.Column('source_publication_date', sa.Date(), nullable=True),
    sa.Column('retrieved_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('artifact_sha256', sa.String(length=64), nullable=False),
    sa.Column('artifact_path', sa.Text(), nullable=False),
    sa.Column('method_version', sa.Text(), nullable=False),
    sa.Column('status', sa.Text(), nullable=False),
    sa.Column('notes', sa.Text(), nullable=False),
    sa.CheckConstraint("artifact_sha256 ~ '^[0-9a-f]{64}$'", name='ck_artifact_sha256'),
    sa.CheckConstraint("status IN ('running', 'succeeded', 'failed')", name='ck_run_status'),
    sa.ForeignKeyConstraint(['source_id'], ['data_source.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'source_id', 'artifact_sha256', name='uq_run_artifact'),
    sa.UniqueConstraint('id', 'source_id', name='uq_run_source')
    )
    op.create_table('metric_definition',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('series_id', sa.Text(), nullable=False),
    sa.Column('label', sa.Text(), nullable=False),
    sa.Column('unit', sa.Text(), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=True),
    sa.Column('geography', sa.Text(), nullable=False),
    sa.Column('covered_population', sa.Text(), nullable=False),
    sa.Column('measure_type', sa.Text(), nullable=False),
    sa.Column('methodology_notes', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['source_id'], ['data_source.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'source_id', name='uq_metric_source'),
    sa.UniqueConstraint('series_id')
    )
    op.create_table('market_observation',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('metric_id', sa.Integer(), nullable=False),
    sa.Column('source_id', sa.Integer(), nullable=False),
    sa.Column('ingestion_run_id', sa.Integer(), nullable=False),
    sa.Column('artifact_sha256', sa.String(length=64), nullable=False),
    sa.Column('observation_date', sa.Date(), nullable=True),
    sa.Column('report_year', sa.Integer(), nullable=True),
    sa.Column('delivery_year', sa.Integer(), nullable=True),
    sa.Column('contract_type', sa.Text(), nullable=True),
    sa.Column('scenario', sa.Text(), nullable=True),
    sa.Column('raw_value', sa.Text(), nullable=False),
    sa.Column('normalized_value', sa.Numeric(precision=24, scale=8), nullable=True),
    sa.Column('value_status', sa.Text(), nullable=False),
    sa.Column('data_status', sa.Text(), nullable=False),
    sa.Column('quality_notes', sa.Text(), nullable=False),
    sa.Column('supersedes_observation_id', sa.Integer(), nullable=True),
    sa.CheckConstraint("(value_status = 'available' AND normalized_value IS NOT NULL) OR (value_status IN ('withheld', 'missing') AND normalized_value IS NULL)", name='ck_value_presence'),
    sa.CheckConstraint("data_status IN ('observed', 'estimate', 'forecast', 'digitized_estimate', 'revised', 'mock')", name='ck_data_status'),
    sa.CheckConstraint("normalized_value IS NULL OR (normalized_value >= 0 AND normalized_value != 'NaN'::numeric)", name='ck_nonnegative_value'),
    sa.CheckConstraint("value_status IN ('available', 'withheld', 'missing')", name='ck_value_status'),
    sa.CheckConstraint('delivery_year IS NULL OR delivery_year BETWEEN 1 AND 9999', name='ck_delivery_year'),
    sa.CheckConstraint('delivery_year IS NULL OR report_year IS NOT NULL', name='ck_delivery_reporting_period'),
    sa.CheckConstraint('observation_date IS NOT NULL OR report_year IS NOT NULL', name='ck_observation_period'),
    sa.CheckConstraint('report_year IS NULL OR report_year BETWEEN 1 AND 9999', name='ck_report_year'),
    sa.CheckConstraint('supersedes_observation_id IS NULL OR supersedes_observation_id != id', name='ck_no_self_revision'),
    sa.ForeignKeyConstraint(['ingestion_run_id', 'source_id', 'artifact_sha256'], ['ingestion_run.id', 'ingestion_run.source_id', 'ingestion_run.artifact_sha256'], name='fk_observation_artifact'),
    sa.ForeignKeyConstraint(['metric_id', 'source_id'], ['metric_definition.id', 'metric_definition.source_id'], name='fk_observation_metric_source'),
    sa.ForeignKeyConstraint(['supersedes_observation_id', 'metric_id'], ['market_observation.id', 'market_observation.metric_id'], name='fk_revision_metric'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('id', 'metric_id', name='uq_observation_metric'),
    sa.UniqueConstraint('metric_id', 'artifact_sha256', 'observation_date', 'report_year', 'delivery_year', 'contract_type', 'scenario', name='uq_observation_artifact_period', postgresql_nulls_not_distinct=True)
    )


def downgrade():
    op.drop_table("market_observation")
    op.drop_table("ingestion_run")
    op.drop_table("metric_definition")
    op.drop_table("data_source")
