from pydantic import BaseModel
from typing import Optional

class User(BaseModel):
    id: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    provider: str
    access_token: str

class TokenInfo(BaseModel):
    sub: str
    email: str
    name: Optional[str] = None
    picture: Optional[str] = None
    exp: int
    scope: str
    provider: str 