"""
Entry point for Phase10-Intelligence-Core.

Running this module bootstraps the application, creates the schema (for
sqlite-based default settings), and prints a readiness summary. This is a
standalone smoke-check entry point -- no HTTP server, worker, or scheduler
is started, per this phase's explicit scope boundaries.
"""
from __future__ import annotations

from .bootstrap.app import create_application


def main() -> None:
    app = create_application()
    with app.new_session() as session:
        container = app.new_container(session)
        session.commit()
        print("Phase10-Intelligence-Core bootstrapped successfully.")
        print(f"Schema version:   {container.settings.schema_version}")
        print(f"Policy version:   {container.settings.policy_version}")
        print(f"Strategy version: {container.settings.strategy_version}")
        print(f"Database URL:     {container.settings.database_url}")


if __name__ == "__main__":
    main()
