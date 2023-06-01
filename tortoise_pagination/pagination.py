from abc import ABC
from typing import Generic, Type, TypeVar

from fastapi import Query
from pydantic import BaseModel, NonNegativeInt, PositiveInt
from pydantic.generics import GenericModel
from tortoise.contrib.pydantic import PydanticModel
from tortoise.queryset import QuerySet

T = TypeVar("T")
M = TypeVar("M")


# https://github.com/pydantic/pydantic/pull/595
class Page(GenericModel, Generic[T], ABC):
    """Represent a Page of T
    """
    count: NonNegativeInt = 0
    items: list[T]

    class Config:
        arbitrary_types_allowed = True


class Pagination(BaseModel):
    """Represents a Pagination request
    """
    offset: NonNegativeInt | None = None
    limit: PositiveInt = 10

    @classmethod
    def from_query(
        cls,
        offset: NonNegativeInt | None = Query(None),
        limit: NonNegativeInt | None = Query(10)
    ) -> "Pagination":
        return cls(offset=offset, limit=limit)

    def paginate_queryset(self, queryset: QuerySet[M]) -> QuerySet[M]:
        if self.limit is not None:
            queryset = queryset.limit(self.limit)
        if self.offset is not None:
            queryset = queryset.offset(self.offset)
        return queryset

    async def paginated_response(
        self,
        queryset: QuerySet,
        schema: Type[PydanticModel]
    ) -> Page:
        """Returns a page from the given queryset
        """
        paginated_queryset = self.paginate_queryset(queryset)
        pagination_class = Page[schema]
        page = pagination_class(
            items=await schema.from_queryset(paginated_queryset),
            count=await queryset.count()
        )
        return page
