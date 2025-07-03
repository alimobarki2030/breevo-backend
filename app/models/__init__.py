# models/__init__.py
from database import Base
from .user import User

try:
    from .salla import SallaStore, SallaProduct
    __all__ = ["Base", "User", "SallaStore", "SallaProduct"]
except ImportError:
    __all__ = ["Base", "User"]