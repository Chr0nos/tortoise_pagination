from tests.models import Product
from tests.serializers import ProductSerializer
from tortoise_pagination import Page, Pagination


async def test_pagination_simple() -> None:
    await Product.all().delete()
    product = await Product.create(name="Brick", price=12.3, weight=1.2)

    pagination = Pagination(limit=10, offset=0)
    page = await pagination.paginated_response(Product.all(), ProductSerializer)
    assert isinstance(page, Page[ProductSerializer])
    assert page.count == 1
    assert page.items[0].id == product.id

    await product.delete()


async def test_pagination_limit_zero() -> None:
    await Product.all().delete()
    product = await Product.create(name="Brick", price=12.3, weight=1.2)
    pagination = Pagination(limit=0, offset=0)

    page = await pagination.paginated_response(Product.all(), ProductSerializer)

    assert isinstance(page, Page[ProductSerializer])
    assert page.count == 1
    assert isinstance(page.items, list)
    assert not page.items

    await product.delete()
