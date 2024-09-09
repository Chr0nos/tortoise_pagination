from tortoise.contrib.pydantic import pydantic_model_creator

from tests.models import Product

ProductBaseSchema = pydantic_model_creator(Product, include=("id", "price", "weight"))


class ProductSchema(ProductBaseSchema):
    name: str
    price_per_kilograms: float
