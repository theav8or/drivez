# This file makes the api_v1 directory a Python package

# Import the router to make it available when importing from api_v1
from .api_new import router

__all__ = ['router']
