from abc import ABC
from asyncio import TaskGroup
from typing import Generic, Type, TypeVar

from fastapi import HTTPException, Query, status
from pydantic import BaseModel, Field, NonNegativeInt, ValidationError
from tortoise.contrib.pydantic import PydanticModel
from tortoise.queryset import QuerySet

T = TypeVar("T")
M = TypeVar("M")


# https://github.com/pydantic/pydantic/pull/595
class Page(BaseModel, Generic[T], ABC):
    """Represent a Page of T"""

    count: NonNegativeInt = 0
    items: list[T] = Field(default_factory=lambda: [])

    class Config:
        arbitrary_types_allowed = True


async def _count_queryset(queryset: QuerySet) -> int:
    return await queryset.count()


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
        self, queryset: QuerySet, schema: Type[PydanticModel]
    ) -> Page:
        """Returns a page from the given queryset"""
        paginated_queryset = self.paginate_queryset(queryset)
        pagination_class = Page[schema]
        limit = paginated_queryset._limit

        async with TaskGroup() as tg:
            if limit > 0:
                items = tg.create_task(schema.from_queryset(paginated_queryset))
            count = tg.create_task(_count_queryset(queryset))

        page = pagination_class(
            items=(items.result() or []) if limit > 0 else [],
            count=count.result(),
        )
        return page
