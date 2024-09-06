import asyncio
from abc import ABC
from inspect import iscoroutinefunction
from typing import Any, Awaitable, Callable, Generic, Type, TypeVar

from fastapi import HTTPException, Query, status
from pydantic import BaseModel, Field, NonNegativeInt, ValidationError
from tortoise.contrib.pydantic import PydanticModel
from tortoise.queryset import QuerySet

T = TypeVar("T")
M = TypeVar("M")
SCHEMA = TypeVar("SCHEMA", bound=BaseModel)


# https://github.com/pydantic/pydantic/pull/595
class Page(BaseModel, Generic[T], ABC):
    """Represent a Page of T"""

    count: NonNegativeInt = 0
    items: list[T] = Field(default_factory=lambda: [])

    class Config:
        arbitrary_types_allowed = True


class Pagination(BaseModel):
    """Represents a Pagination request"""

    offset: NonNegativeInt | None = None
    limit: NonNegativeInt = 10

    @classmethod
    def from_query(
        cls,
        offset: NonNegativeInt | None = Query(None),
        limit: NonNegativeInt | None = Query(10),
    ) -> "Pagination":
        try:
            return cls(offset=offset, limit=limit)
        except ValidationError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=error.errors()
            )

    def paginate_queryset(self, queryset: QuerySet[M]) -> QuerySet[M]:
        if self.limit is not None:
            queryset = queryset.limit(self.limit)
        if self.offset is not None:
            queryset = queryset.offset(self.offset)
        return queryset

    async def paginated_response(
        self,
        queryset: QuerySet[M],
        schema: Type[PydanticModel],
    ) -> Page:
        """Returns a page from the given queryset"""
        paginated_queryset = self.paginate_queryset(queryset)
        pagination_class = Page[schema]
        limit = paginated_queryset._limit

        tasks = [queryset.count()]
        if limit > 0:
            tasks.append(schema.from_queryset(paginated_queryset))

        count, items = await asyncio.gather(*tasks)
        page = pagination_class(items=items, count=count)
        return page

    async def get_custom_paginated_response(
        self,
        queryset: QuerySet[M],
        schema: Type[PydanticModel],
        extra_fields: dict[
            str, Callable[[M], Any] | Callable[[M], Awaitable[Any] | Any]
        ]
        | None = None,
    ) -> Page[SCHEMA]:
        if extra_fields is None:
            extra_fields = {}

        async def _get_serialized_instance(instance: M) -> SCHEMA:
            for field_name, resolver in extra_fields.items():
                if iscoroutinefunction(resolver):
                    field_value = await resolver(instance)
                else:
                    field_value = resolver(instance)
                setattr(instance, field_name, field_value)

            return await schema.from_tortoise_orm(instance)

        items_tasks = [
            _get_serialized_instance(instance) async for instance in queryset
        ]
        count, items = await asyncio.gather(queryset.count(), *items_tasks)

        pagination_class = Page[schema]
        pagination_instance = pagination_class(count=count, items=items)

        return pagination_instance
