from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from utils import get_current_user

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
