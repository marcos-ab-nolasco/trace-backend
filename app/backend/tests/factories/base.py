"""Base factory for async SQLAlchemy models."""

from typing import Any, TypeVar

from factory.alchemy import SQLAlchemyModelFactory
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


class AsyncSQLAlchemyFactory(SQLAlchemyModelFactory):
    """Base factory for async SQLAlchemy models.

    This factory extends SQLAlchemyModelFactory to support async database sessions.
    The session must be set via _meta.sqlalchemy_session before creating instances.
    """

    class Meta:
        abstract = True
        sqlalchemy_session_persistence = "commit"

    @classmethod
    async def create_async(cls, **kwargs: Any) -> Any:
        """Create and persist an instance asynchronously.

        Supports get_or_create behavior if sqlalchemy_get_or_create is configured.

        Args:
            **kwargs: Attributes to override in the created instance

        Returns:
            The created and persisted model instance
        """
        from sqlalchemy import select

        session: AsyncSession = cls._meta.sqlalchemy_session

        # Check if get_or_create is configured
        get_or_create_fields = getattr(cls._meta, "sqlalchemy_get_or_create", None)

        if get_or_create_fields:
            # Extract the field values from kwargs (before building)
            model = cls._meta.model
            filters = []

            # Try to get values from kwargs or generate them
            for field in get_or_create_fields:
                if field in kwargs:
                    value = kwargs[field]
                else:
                    # Need to get default value from factory declarations
                    stub = cls.stub(**kwargs)
                    value = getattr(stub, field)

                filters.append(getattr(model, field) == value)

            # Try to find existing
            stmt = select(model).where(*filters)
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing:
                return existing

        # If not found or get_or_create not configured, create new
        instance = cls.build(**kwargs)
        session.add(instance)
        await session.commit()
        await session.refresh(instance)

        return instance

    @classmethod
    async def create_batch_async(cls, size: int, **kwargs: Any) -> list[Any]:
        """Create and persist multiple instances asynchronously.

        Args:
            size: Number of instances to create
            **kwargs: Attributes to override in all created instances

        Returns:
            List of created and persisted model instances
        """
        session: AsyncSession = cls._meta.sqlalchemy_session

        instances = [cls.build(**kwargs) for _ in range(size)]

        session.add_all(instances)
        await session.commit()

        for instance in instances:
            await session.refresh(instance)

        return instances
