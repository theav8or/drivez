from typing import Optional, Type, TypeVar, List
from httpx import Response
from app.exceptions.scraping import (
    ScrapingError, NetworkError, RateLimitError,
    AuthenticationError, DataProcessingError,
    RetryableError, FatalError
)

E = TypeVar('E', bound=Exception)

class ErrorHandler:
    @staticmethod
    def handle_scraping_error(
        error: Exception,
        response: Optional[Response] = None,
        retryable: bool = True
    ) -> ScrapingError:
        """Converts raw exceptions into specific scraping errors"""
        if isinstance(error, ScrapingError):
            return error

        if isinstance(error, (ConnectionError, TimeoutError)):
            return NetworkError("Network connection failed", response)
        
        if isinstance(error, (ValueError, TypeError)):
            return DataProcessingError("Data processing failed", response)
        
        if isinstance(error, PermissionError):
            return AuthenticationError("Authentication failed", response)
        
        if isinstance(error, RateLimitError):
            return RateLimitError("Rate limit exceeded", response)
            
        if retryable:
            return RetryableError(
                f"Retryable error occurred: {str(error)}",
                response
            )
            
        return FatalError(
            f"Fatal error occurred: {str(error)}",
            response
        )

    @staticmethod
    def analyze_response(response: Response) -> Optional[ScrapingError]:
        """Analyzes HTTP response for common scraping issues"""
        if response.status_code == 429:
            return RateLimitError("Rate limit exceeded", response)
        
        if response.status_code == 401:
            return AuthenticationError("Authentication failed", response)
            
        if response.status_code == 403:
            return RateLimitError("Access denied", response)
            
        if response.status_code >= 500:
            return RetryableError(
                f"Server error: {response.status_code}",
                response
            )
            
        return None

    @staticmethod
    def get_retry_delay(error: ScrapingError, attempt: int) -> float:
        """Calculate appropriate retry delay based on error type"""
        base_delay = 2.0  # base delay in seconds
        
        if isinstance(error, RateLimitError):
            return base_delay * (2 ** attempt)  # exponential backoff for rate limits
            
        if isinstance(error, NetworkError):
            return base_delay * (1.5 ** attempt)  # faster retry for network issues
            
        return base_delay * (1.2 ** attempt)  # default exponential backoff

    @staticmethod
    def should_retry(error: ScrapingError) -> bool:
        """Determine if we should retry based on error type"""
        return not isinstance(error, (FatalError, AuthenticationError))
