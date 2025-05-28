from typing import Optional
from httpx import Response

class ScrapingError(Exception):
    """Base class for all scraping-related errors"""
    def __init__(self, message: str, response: Optional[Response] = None):
        self.message = message
        self.response = response
        super().__init__(message)

class NetworkError(ScrapingError):
    """Raised when there's a network-related issue"""
    pass

class RateLimitError(ScrapingError):
    """Raised when we hit rate limits"""
    pass

class AuthenticationError(ScrapingError):
    """Raised when authentication fails"""
    pass

class DataProcessingError(ScrapingError):
    """Raised when data processing fails"""
    pass

class RetryableError(ScrapingError):
    """Raised when error is potentially retryable"""
    pass

class FatalError(ScrapingError):
    """Raised when error is not recoverable"""
    pass
