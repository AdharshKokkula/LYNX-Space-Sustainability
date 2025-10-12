"""
Configuration loader for LLM and system settings.
Loads configuration from JSON files and environment variables.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from pathlib import Path
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()


class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass


class ConfigLoader:
    """Loads and validates system configuration."""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize configuration loader.
        
        Args:
            config_path: Path to llm_config.json file. If None, uses default path.
        """
        if config_path is None:
            # Default path relative to this file
            config_dir = Path(__file__).parent
            config_path = config_dir / "llm_config.json"
        
        self.config_path = Path(config_path)
        self._config = None
        self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from JSON file."""
        try:
            if not self.config_path.exists():
                logger.warning(f"Config file not found: {self.config_path}. Using defaults.")
                self._config = self._get_default_config()
                return
            
            with open(self.config_path, 'r') as f:
                self._config = json.load(f)
            
            logger.info(f"Configuration loaded from {self.config_path}")
            
            # Override with environment variables
            self._apply_env_overrides()
            
            # Validate configuration
            self._validate_config()
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise ConfigurationError(f"Invalid JSON in config file: {e}")
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            raise ConfigurationError(f"Error loading configuration: {e}")
    
    def _apply_env_overrides(self) -> None:
        """Override configuration with environment variables."""
        # API Key
        api_key = os.getenv('HUGGINGFACE_API_KEY')
        if api_key:
            self._config['api_key'] = api_key
        
        # Model name
        model_name = os.getenv('LLM_MODEL_NAME')
        if model_name:
            self._config['model_name'] = model_name
        
        # Cache settings
        cache_enabled = os.getenv('CACHE_ENABLED')
        if cache_enabled is not None:
            self._config['cache_config']['enabled'] = cache_enabled.lower() == 'true'
        
        cache_ttl = os.getenv('CACHE_TTL_SECONDS')
        if cache_ttl:
            self._config['cache_config']['ttl_seconds'] = int(cache_ttl)
        
        cache_max_size = os.getenv('CACHE_MAX_SIZE')
        if cache_max_size:
            self._config['cache_config']['max_size'] = int(cache_max_size)
        
        # Report settings
        timeout = os.getenv('REPORT_TIMEOUT_SECONDS')
        if timeout:
            self._config['retry_config']['timeout_seconds'] = int(timeout)
        
        max_retries = os.getenv('REPORT_MAX_RETRIES')
        if max_retries:
            self._config['retry_config']['max_retries'] = int(max_retries)
    
    def _validate_config(self) -> None:
        """Validate configuration values."""
        # Validate provider
        if self._config.get('provider') not in ['huggingface', 'local']:
            raise ConfigurationError(f"Invalid provider: {self._config.get('provider')}")
        
        # Validate model name
        if not self._config.get('model_name'):
            raise ConfigurationError("Model name is required")
        
        # Validate API key format (if provided)
        api_key = self._config.get('api_key')
        if api_key and not api_key.startswith('hf_'):
            logger.warning("API key does not start with 'hf_'. This may be invalid.")
        
        # Validate numeric parameters
        params = self._config.get('parameters', {})
        
        max_tokens = params.get('max_tokens', 1500)
        if not isinstance(max_tokens, int) or max_tokens < 100 or max_tokens > 4000:
            raise ConfigurationError(f"Invalid max_tokens: {max_tokens}. Must be between 100 and 4000.")
        
        temperature = params.get('temperature', 0.7)
        if not isinstance(temperature, (int, float)) or temperature < 0 or temperature > 2:
            raise ConfigurationError(f"Invalid temperature: {temperature}. Must be between 0 and 2.")
        
        top_p = params.get('top_p', 0.9)
        if not isinstance(top_p, (int, float)) or top_p < 0 or top_p > 1:
            raise ConfigurationError(f"Invalid top_p: {top_p}. Must be between 0 and 1.")
        
        # Validate retry config
        retry_config = self._config.get('retry_config', {})
        max_retries = retry_config.get('max_retries', 2)
        if not isinstance(max_retries, int) or max_retries < 0 or max_retries > 5:
            raise ConfigurationError(f"Invalid max_retries: {max_retries}. Must be between 0 and 5.")
        
        timeout = retry_config.get('timeout_seconds', 30)
        if not isinstance(timeout, int) or timeout < 5 or timeout > 120:
            raise ConfigurationError(f"Invalid timeout_seconds: {timeout}. Must be between 5 and 120.")
        
        logger.info("Configuration validation passed")
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Return default configuration."""
        return {
            "provider": "huggingface",
            "model_name": "mistralai/Mistral-7B-Instruct-v0.2",
            "api_key": os.getenv('HUGGINGFACE_API_KEY'),
            "fallback_models": [
                "HuggingFaceH4/zephyr-7b-beta"
            ],
            "parameters": {
                "max_tokens": 1500,
                "temperature": 0.7,
                "top_p": 0.9
            },
            "retry_config": {
                "max_retries": 2,
                "backoff_factor": 2,
                "timeout_seconds": 30
            },
            "cache_config": {
                "enabled": True,
                "max_size": 100,
                "ttl_seconds": 3600
            },
            "report_config": {
                "include_mission_info": True,
                "include_recommendations": True,
                "risk_thresholds": {
                    "high": 10,
                    "medium": 100
                }
            }
        }
    
    def get_config(self) -> Dict[str, Any]:
        """Get the loaded configuration."""
        return self._config.copy()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a configuration value by key."""
        return self._config.get(key, default)
    
    def reload(self) -> None:
        """Reload configuration from file."""
        logger.info("Reloading configuration...")
        self._load_config()


# Global configuration instance
_config_loader = None


def get_config_loader() -> ConfigLoader:
    """Get the global configuration loader instance."""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader


def get_config() -> Dict[str, Any]:
    """Get the current configuration."""
    return get_config_loader().get_config()
