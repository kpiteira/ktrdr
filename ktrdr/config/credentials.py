"""
Secure handling of credentials for KTRDR.

This module provides utilities for securely loading and validating API credentials
and other sensitive information from environment variables.
"""

import os
from typing import Any, Dict, Optional, Union

from pydantic import BaseModel, Field, model_validator

from ktrdr import get_logger
from ktrdr.errors import (
    ConfigurationError,
    InvalidConfigurationError,
    MissingConfigurationError,
)

logger = get_logger(__name__)


class CredentialProvider:
    """
    Provides secure access to API credentials and sensitive configuration.

    This class retrieves credentials from environment variables following
    secure practices and provides validation.
    """

    @staticmethod
    def get_credential(
        env_var: str, default: Optional[str] = None, required: bool = True
    ) -> Optional[str]:
        """
        Retrieve a credential from an environment variable.

        Args:
            env_var: Name of the environment variable to retrieve
            default: Optional default value if environment variable is not set
            required: Whether the credential is required (raises error if missing)

        Returns:
            The credential value as a string, or default if not required

        Raises:
            MissingConfigurationError: If the credential is required but not found
        """
        value = os.environ.get(env_var, default)

        if required and value is None:
            raise MissingConfigurationError(
                message=f"Required credential {env_var} not found in environment",
                error_code="SEC-MissingCredential",
                details={"env_var": env_var},
            )

        return value

    @staticmethod
    def validate_credential(
        value: Optional[str], validation_func: callable, error_message: str
    ) -> None:
        """
        Validate a credential against specified criteria.

        Args:
            value: The credential value to validate
            validation_func: A function that returns True if valid
            error_message: Error message to include if validation fails

        Raises:
            InvalidConfigurationError: If validation fails
        """
        if value is not None and not validation_func(value):
            raise InvalidConfigurationError(
                message=error_message,
                error_code="SEC-ValidationFailed",
                details={"validation_failed": True},
            )


class APICredentials(BaseModel):
    """Base model for API credentials validation."""

    @model_validator(mode="before")
    @classmethod
    def ensure_no_empty_strings(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Ensure no credential is an empty string."""
        if not isinstance(data, dict):
            return data

        for field_name, value in data.items():
            if isinstance(value, str) and value.strip() == "":
                data[field_name] = None
        return data


class InteractiveBrokersCredentials(APICredentials):
    """Credentials model for Interactive Brokers API."""

    username: Optional[str] = Field(None, description="IB API username")
    account_id: Optional[str] = Field(None, description="IB account ID")
    api_key: Optional[str] = Field(None, description="IB API key")

    @classmethod
    def from_env(cls) -> "InteractiveBrokersCredentials":
        """
        Create credentials object from environment variables.

        Environment variables used:
        - KTRDR_IB_USERNAME: IB API username
        - KTRDR_IB_ACCOUNT_ID: IB account ID
        - KTRDR_IB_API_KEY: IB API key

        Returns:
            An InteractiveBrokersCredentials instance
        """
        provider = CredentialProvider()

        # Get credentials from environment with non-required defaults
        username = provider.get_credential("KTRDR_IB_USERNAME", required=False)
        account_id = provider.get_credential("KTRDR_IB_ACCOUNT_ID", required=False)
        api_key = provider.get_credential("KTRDR_IB_API_KEY", required=False)

        return cls(username=username, account_id=account_id, api_key=api_key)

    def is_complete(self) -> bool:
        """Check if all required credentials are present."""
        return all([self.username, self.account_id, self.api_key])


def get_credentials(provider_name: str) -> Union[APICredentials, None]:
    """
    Get credentials for a specific provider.

    Args:
        provider_name: Name of the credentials provider (e.g., 'interactive_brokers')

    Returns:
        An APICredentials instance for the specified provider

    Raises:
        ConfigurationError: If the provider name is invalid
    """
    providers = {"interactive_brokers": InteractiveBrokersCredentials.from_env}

    if provider_name not in providers:
        raise ConfigurationError(
            message=f"Unknown credentials provider: {provider_name}",
            error_code="SEC-UnknownProvider",
            details={"available_providers": list(providers.keys())},
        )

    return providers[provider_name]()
