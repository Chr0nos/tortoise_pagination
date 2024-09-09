import asyncio
from abc import ABC
from inspect import iscoroutinefunction
from typing import Any, Awaitable, Callable, Generic, Type, TypeVar

from fastapi import HTTPException, Query, status
from pydantic import BaseModel, Field, NonNegativeInt, ValidationError, create_model
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


async def count_queryset_safe(queryset: QuerySet) -> int:
    try:
        return max(await queryset.count(), 0)
    # for some reasons the ORM raises an error if nothing matches the offset
    # IndexError: list index out of range
    except IndexError:
        return 0


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

        count = await count_queryset_safe(queryset)
        if not count:
            items = []
        else:
            items = await schema.from_queryset(paginated_queryset)

        page = pagination_class(items=items, count=max(count, 0))
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
        """Generate a paginated response using the `extra_fields`,
        keys are the fields name, values are the value returned by the callable
        you can pass `user_data` to use extra data in the awaitable function
        that data will be available in the second argument
        """

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

        count = await count_queryset_safe(queryset)
        paginated_queryset = self.paginate_queryset(queryset)

        # don't call the paginated_queryset if there is no count otherwise the
        # orm raise an error instead of an empty list...
        # that's why we can't do the count in // of fetching the items.
        if paginated_queryset._limit > 0 and count:
            items = await asyncio.gather(
                *[
                    _get_serialized_instance(instance)
                    async for instance in paginated_queryset
                ]
            )
        else:
            items = []

        pagination_class = Page[schema]
        pagination_instance = pagination_class(count=count, items=items)

        return pagination_instance


def build_pydantic_model_with_extra_fields(
    from_model: M,
    name: str,
    extra_fields: dict[str, Callable[[M], Any] | Callable[[M], Awaitable[Any] | Any]],
    **kwargs,
) -> BaseModel:
    """Builds a new model with extra fields annotated in it from the given model"""
    fields = {
        field_name: (field_callable.__annotations__["return"], ...)
        for field_name, field_callable in extra_fields.items()
    }
    model = create_model(name, **fields, __base__=from_model, **kwargs)
    return model
