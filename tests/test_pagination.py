from tests.models import Product
from tests.schemas import ProductBaseSchema, ProductSchema
from tortoise_pagination import Page, Pagination, build_pydantic_model_with_extra_fields


async def test_pagination_simple() -> None:
    await Product.all().delete()
    product = await Product.create(name="Brick", price=12.3, weight=1.2)

    pagination = Pagination(limit=10, offset=0)
    page = await pagination.paginated_response(Product.all(), ProductBaseSchema)
    assert isinstance(page, Page[ProductBaseSchema])
    assert page.count == 1
    assert page.items[0].id == product.id

    await product.delete()


async def test_pagination_limit_zero() -> None:
    await Product.all().delete()
    product = await Product.create(name="Brick", price=12.3, weight=1.2)
    pagination = Pagination(limit=0, offset=0)

    page = await pagination.paginated_response(Product.all(), ProductBaseSchema)

    assert isinstance(page, Page[ProductBaseSchema])
    assert page.count == 1
    assert isinstance(page.items, list)
    assert not page.items

    await product.delete()


async def test_pagination_extra_fields() -> None:
    def _price_per_kilograms(product: Product) -> float:
        return product.price / product.weight

    async def _kilograms_to_pounds(product: Product) -> float:
        return product.weight * 2.204623

    extra_fields = {
        "title": lambda product: product.name.title,
        "price_per_kilograms": _price_per_kilograms,
        "pounds": _kilograms_to_pounds,
    }
    new_schema = build_pydantic_model_with_extra_fields(
        ProductSchema,
        "ProductSchemaWithExtras",
        extra_fields,
    )
    assert issubclass(new_schema, ProductSchema)

    await Product.all().delete()
    product = await Product.create(name="my awesome product", price=12.3, weight=1.2)

    pagination = Pagination(offset=0, limit=10)
    page = await pagination.get_custom_paginated_response(
        Product.all(), new_schema, extra_fields
    )
    assert isinstance(page.items, list)
    for item in page.items:
        assert isinstance(item, new_schema)
    assert page.items[0].title == "My Awesome Product"
    assert page.items[0].price_per_kilograms == 12.3 / 1.2
    assert page.items[0].pounds == product.weight * 2.204623

    await product.delete()
