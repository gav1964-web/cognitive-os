from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class ItemRequest(BaseModel):
    sku: str
    quantity: int


class ItemResponse(BaseModel):
    sku: str
    total: float


def price_item(req: ItemRequest) -> ItemResponse:
    return ItemResponse(sku=req.sku, total=req.quantity * 3.5)


@app.post("/items")
def create_item(req: ItemRequest) -> ItemResponse:
    return price_item(req)
