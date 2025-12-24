"""SQLAlchemy declarative base for database models.

This module provides the base class for all SQLAlchemy ORM models.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy ORM models.

    All database models should inherit from this class. This provides
    the declarative base for table creation and metadata management.
    """

    pass
