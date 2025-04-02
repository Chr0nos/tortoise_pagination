from tortoise_serializer import ModelSerializer

from .models import Product


class ProductSerializer(ModelSerializer[Product]):
    id: int
    price: float
    weight: float
