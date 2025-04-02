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
