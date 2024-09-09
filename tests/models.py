from tortoise import fields
from tortoise.models import Model


class Product(Model):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=100)
    price = fields.FloatField()
    weight = fields.FloatField()
