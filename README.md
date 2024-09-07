# Usage
Supposing in `myapp.schema` you have a pydantic `BaseModel` to represent your model

```python
from fastapi import Depends
from tortoise_pagination import Pagination, Page

from myapp.main import app
from myapp.models import MyModel
from myapp.schema import MySchema


@app.get('/mymodel')
async def my_view(pagination: Depends(Pagination.from_query)) -> Page[MySchema]:
    return await pagination.paginated_response(MyModel.all(), MySchema)
```

now you can request with:
```shell
curl http://localhost:8000/mymodel?offset=0&limit=20
```

returned structure:
- items list[MySchema]
- count: NonNegativeInt -> the number of entries for this queryset
  (`MyModel.all().count()`) wich the frontend will need to be able to display a pagination


# Computed field
Sometime you may want to add computed fields, however pydantic is not async capable so sometime it may become a challenge
to achieve that we do:

```python
from fastapi import Depends
from fastapi.routing import APIRouter
from myapp.models import Product
from tortoise.contrib.pydantic import pydantic_model_creator

from tortoise_pagination import Page, Pagination

ProductBaseSchema = pydantic_model_creator(Product, include=("id", "price", "weight"))


class ProductSchema(ProductBaseSchema):
    name: str
    price_per_kilogram: float | None


router = APIRouter(prefix="products")


async def _compute_price_per_kilogram(product: Product) -> float | None:
    try:
        return product.price / product.weight
    except ZeroDivisionError:
        return None


@router.get("")
async def list_products(
    pagination: Depends(Pagination.from_query),
) -> Page[ProductSchema]:
    products = Products.all()
    return await pagination.get_custom_paginated_response(
        queryset=products,
        schema=ProductSchema,
        extra_fields={
            "name": lambda product: product.name.title(),
            "price_per_kilogram": _compute_price_per_kilogram,
        },
    )

```
