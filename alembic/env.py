from alembic import context
from app.database import make_engine
from app.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_online() -> None:
    # DATABASE_URL (env/.env) is the single source of truth; allow override via -x url=...
    url = context.get_x_argument(as_dictionary=True).get("url")
    engine = make_engine(url)
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=connection.dialect.name == "sqlite",
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
