from alembic import context
from app.config import get_settings
from app.database import make_engine
from app.models import Base

config = context.config
target_metadata = Base.metadata


def run_migrations_online() -> None:
    settings = get_settings()
    # Neon migrations need the direct URL; keep DATABASE_URL pooled for app traffic.
    url = (
        context.get_x_argument(as_dictionary=True).get("url")
        or settings.database_url_unpooled
        or settings.database_url
    )
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
