# models/__init__.py
from database import Base
from .user import User
from .salla import SallaStore, SallaProduct

# تصدير جميع النماذج
__all__ = ["Base", "User", "SallaStore", "SallaProduct"]