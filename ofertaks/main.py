"""Application entrypoint."""

from __future__ import annotations


def run() -> None:
    from ofertaks.app.paths import ensure_app_dirs, get_database_path
    from ofertaks.database.database import Database
    from ofertaks.database.repository import Repository
    from ofertaks.ui.root import OfertaKSApp

    ensure_app_dirs()
    database = Database(get_database_path())
    repository = Repository(database)
    repository.initialize()
    OfertaKSApp(repository=repository).run()


if __name__ == "__main__":
    run()
