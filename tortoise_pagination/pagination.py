import asyncio
from abc import ABC
from inspect import iscoroutinefunction
from typing import Any, Awaitable, Callable, Generic, Sequence, Type, TypeVar

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

    async def _page_response(
        self,
        pagination_class,
        tasks: Sequence[Awaitable],
    ) -> Page:
        """Returns a `Page[pagination_class]`
        first element of `tasks` must be the count method of the queryset
        """
        count, *items = await asyncio.gather(*tasks)

        if items and isinstance(items[0], list):
            items = items[0]

        page = pagination_class(
            items=items,
            count=max(count, 0),
        )
        return page

    async def paginated_response(
        self,
        queryset: QuerySet[M],
        schema: Type[PydanticModel],
    ) -> Page:
        """Returns a page from the given queryset"""
        paginated_queryset = self.paginate_queryset(queryset)
        pagination_class = Page[schema]

        tasks = [queryset.count()]
        # don't call the queryset if the limit is 0
        if paginated_queryset._limit > 0:
            tasks.append(schema.from_queryset(paginated_queryset))

        return await self._page_response(pagination_class, tasks)

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

        paginated_queryset = self.paginate_queryset(queryset)

        tasks = [queryset.count()]
        # don't call the queryset if the limit is 0
        if paginated_queryset._limit > 0:
            tasks.extend(
                [
                    _get_serialized_instance(instance)
                    async for instance in paginated_queryset
                ]
            )

        pagination_class = Page[schema]
        return await self._page_response(pagination_class, tasks)


def build_pydantic_model_with_extra_fields(
    from_model: M,
    name: str,
    extra_fields: dict[str, Callable[[M], Any] | Callable[[M], Awaitable[Any] | Any]],
    **kwargs,
) -> BaseModel:
    """Builds a new model with extra fields annotated in it from the given model"""
    fields = {
        field_name: (field_callable.__annotations__.get("return", Any), ...)
        for field_name, field_callable in extra_fields.items()
    }
    model = create_model(name, **fields, __base__=from_model, **kwargs)
    return model
