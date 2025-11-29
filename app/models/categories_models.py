from pydantic import BaseModel, ConfigDict

class CategoryCreate(BaseModel):
    name: str


class Category(CategoryCreate):
    id: int
    model_config = ConfigDict(from_attributes=True)