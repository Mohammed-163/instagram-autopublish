"""
UnitOfWork abstraction.

Encapsulates a single database transaction boundary.
Contains no business logic — only commit/rollback semantics.
Used as a context manager: `with uow: ...`.
"""
from __future__ import annotations

from types import TracebackType
from typing import Optional, Type

from sqlalchemy.orm import Session

from observation.infrastructure.db.connection import DatabaseConnectionFactory


class UnitOfWork:
    """
    Manages a single SQLAlchemy Session for one logical operation.

    Usage:
        with UnitOfWork(factory) as uow:
            uow.session.add(some_orm_object)
            uow.commit()         # explicit commit
        # rollback called automatically on exception

    The application layer (or repository) receives a reference to
    `uow.session`; it never creates sessions itself.
    """

    def __init__(self, factory: DatabaseConnectionFactory) -> None:
        self._factory = factory
        self._session: Optional[Session] = None

    # ------------------------------------------------------------------
    # Context-manager protocol
    # ------------------------------------------------------------------

    def __enter__(self) -> "UnitOfWork":
        self._session = self._factory.new_session()
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> bool:
        if exc_type is not None:
            self.rollback()
        self._close()
        return False  # never suppress exceptions

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def session(self) -> Session:
        if self._session is None:
            raise RuntimeError("UnitOfWork not entered.  Use as a context manager.")
        return self._session

    def commit(self) -> None:
        """Flush pending changes and commit the transaction."""
        self.session.commit()

    def rollback(self) -> None:
        """Discard all pending changes."""
        if self._session is not None:
            self._session.rollback()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _close(self) -> None:
        if self._session is not None:
            self._session.close()
            self._session = None
