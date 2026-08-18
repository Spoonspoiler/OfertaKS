"""Application entrypoint."""

from __future__ import annotations


def run() -> None:
    from ofertaks.app.config import get_data_dir
    from ofertaks.database.database import Database
    from ofertaks.database.repository import Repository
    from ofertaks.ui.root import OfertaKSApp

    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    database = Database(data_dir / "ofertaks.sqlite3")
    repository = Repository(database)
    repository.initialize()
    OfertaKSApp(repository=repository).run()


if __name__ == "__main__":
    run()
