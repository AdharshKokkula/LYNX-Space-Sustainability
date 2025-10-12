"""
LLM client for interacting with Hugging Face Inference API.
Handles text generation with retry logic and error handling.
"""
import logging
import time
import requests
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


class LLMAPIError(LLMError):
    """Raised when LLM API returns an error."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when LLM request times out."""
    pass


class LLMRateLimitError(LLMError):
    """Raised when rate limit is exceeded."""
    pass


class HuggingFaceLLMClient:
    """Client for Hugging Face Inference API."""
    
    def __init__(self, api_key: Optional[str] = None, model_name: str = "mistralai/Mistral-7B-Instruct-v0.2",
                 timeout: int = 30, max_retries: int = 2, backoff_factor: float = 2.0):
        """
        Initialize Hugging Face LLM client.
        
        Args:
            api_key: Hugging Face API key (optional for free tier)
            model_name: Name of the model to use
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
            backoff_factor: Exponential backoff multiplier
        """
        self.api_key = api_key
        self.model_name = model_name
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor
        self.base_url = "https://api-inference.huggingface.co/models"
        
        # Statistics
        self._stats = {
            'requests': 0,
            'successes': 0,
            'failures': 0,
            'retries': 0,
            'total_tokens': 0,
            'total_time': 0.0
        }
        
        logger.info(f"LLM client initialized: model={model_name}, timeout={timeout}s")
    
    def generate_text(self, prompt: str, max_tokens: int = 1500, 
                     temperature: float = 0.7, top_p: float = 0.9) -> str:
        """
        Generate text using the LLM.
        
        Args:
            prompt: Input prompt for the model
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0-2)
            top_p: Nucleus sampling parameter (0-1)
            
        Returns:
            Generated text string
            
        Raises:
            LLMAPIError: If API returns an error
            LLMTimeoutError: If request times out
            LLMRateLimitError: If rate limit is exceeded
        """
        start_time = time.time()
        self._stats['requests'] += 1
        
        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": max_tokens,
                "temperature": temperature,
                "top_p": top_p,
                "return_full_text": False
            }
        }
        
        try:
            response_data = self._make_request_with_retry(payload)
            generated_text = self._extract_text(response_data)
            
            # Update statistics
            elapsed = time.time() - start_time
            self._stats['successes'] += 1
            self._stats['total_time'] += elapsed
            self._stats['total_tokens'] += len(generated_text.split())
            
            logger.info(f"Text generated successfully in {elapsed:.2f}s")
            return generated_text
            
        except Exception as e:
            self._stats['failures'] += 1
            logger.error(f"Text generation failed: {e}")
            raise
    
    def _make_request_with_retry(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make API request with exponential backoff retry.
        
        Args:
            payload: Request payload
            
        Returns:
            Response data dict
            
        Raises:
            LLMAPIError: If all retries fail
            LLMTimeoutError: If request times out
            LLMRateLimitError: If rate limited
        """
        url = f"{self.base_url}/{self.model_name}"
        headers = {
            "Content-Type": "application/json"
        }
        
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                if attempt > 0:
                    # Exponential backoff
                    wait_time = self.backoff_factor ** attempt
                    logger.info(f"Retry attempt {attempt}/{self.max_retries} after {wait_time}s")
                    time.sleep(wait_time)
                    self._stats['retries'] += 1
                
                response = requests.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                    verify=True  # SSL verification
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', 60))
                    raise LLMRateLimitError(f"Rate limit exceeded. Retry after {retry_after}s")
                
                # Handle model loading (503 with specific message)
                if response.status_code == 503:
                    error_data = response.json()
                    if 'estimated_time' in error_data:
                        wait_time = error_data['estimated_time']
                        logger.info(f"Model loading, waiting {wait_time}s...")
                        time.sleep(min(wait_time, 20))  # Cap at 20 seconds
                        continue
                
                # Handle other errors
                if response.status_code != 200:
                    error_msg = response.text
                    raise LLMAPIError(f"API error {response.status_code}: {error_msg}")
                
                return response.json()
                
            except requests.Timeout as e:
                last_exception = LLMTimeoutError(f"Request timed out after {self.timeout}s")
                logger.warning(f"Request timeout on attempt {attempt + 1}")
                
            except requests.RequestException as e:
                last_exception = LLMAPIError(f"Request failed: {str(e)}")
                logger.warning(f"Request failed on attempt {attempt + 1}: {e}")
                
            except LLMRateLimitError as e:
                # Don't retry on rate limit
                raise
        
        # All retries exhausted
        if last_exception:
            raise last_exception
        else:
            raise LLMAPIError("All retry attempts failed")
    
    def _extract_text(self, response_data: Any) -> str:
        """
        Extract generated text from API response.
        
        Args:
            response_data: API response data
            
        Returns:
            Generated text string
            
        Raises:
            LLMAPIError: If response format is invalid
        """
        try:
            # Handle different response formats
            if isinstance(response_data, list) and len(response_data) > 0:
                if isinstance(response_data[0], dict):
                    return response_data[0].get('generated_text', '')
                elif isinstance(response_data[0], str):
                    return response_data[0]
            elif isinstance(response_data, dict):
                return response_data.get('generated_text', '')
            elif isinstance(response_data, str):
                return response_data
            
            raise LLMAPIError(f"Unexpected response format: {type(response_data)}")
            
        except Exception as e:
            raise LLMAPIError(f"Failed to extract text from response: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get client statistics.
        
        Returns:
            Dict with request statistics
        """
        avg_time = (self._stats['total_time'] / self._stats['successes'] 
                   if self._stats['successes'] > 0 else 0)
        
        return {
            **self._stats,
            'avg_time_seconds': round(avg_time, 2),
            'success_rate': round(
                (self._stats['successes'] / self._stats['requests'] * 100) 
                if self._stats['requests'] > 0 else 0, 
                2
            )
        }
    
    def test_connection(self) -> bool:
        """
        Test connection to the API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            test_prompt = "Hello, this is a test."
            self.generate_text(test_prompt, max_tokens=10)
            logger.info("Connection test successful")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
