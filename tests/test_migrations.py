"""Миграции создают ровно те таблицы, которые описаны в моделях."""

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect


def test_migrations_match_models(tmp_path):
    url = f"sqlite:///{(tmp_path / 'test.db').as_posix()}"
    config = Config("alembic.ini")
    config.set_main_option("sqlalchemy.url", url)

    command.upgrade(config, "head")
    command.check(config)  # упадёт, если модели ушли вперёд, а миграцию забыли

    engine = create_engine(url)
    try:
        assert {"campaign_defaults", "created_campaigns"} <= set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    command.downgrade(config, "base")
