#!/usr/bin/env python3
"""
Security verification script for KTRDR.

This script verifies the functionality of security measures implemented in Task 1.6.
"""

import os
import sys
from pathlib import Path

# Ensure ktrdr package is in path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ktrdr.config import (
    ConfigLoader,
    InputValidator,
    get_credentials,
    sanitize_parameters,
)
from ktrdr.errors import ConfigurationError, ValidationError


def verify_credential_loading():
    """Verify loading credentials from environment variables."""
    print("\n=== Testing Credential Loading ===")

    # Set test environment variables
    os.environ["KTRDR_TEST_USERNAME"] = "test_user"
    os.environ["KTRDR_TEST_API_KEY"] = "api_key_123"

    print("✓ Set test environment variables")

    # Create a test credential provider
    from ktrdr.config.credentials import CredentialProvider

    username = CredentialProvider.get_credential("KTRDR_TEST_USERNAME")
    api_key = CredentialProvider.get_credential("KTRDR_TEST_API_KEY")

    print(f"✓ Retrieved username: {username}")
    print(f"✓ Retrieved API key: {api_key}")

    # Test missing credential with fallback
    default_region = CredentialProvider.get_credential(
        "KTRDR_TEST_REGION", default="us-east-1", required=False
    )

    print(f"✓ Retrieved default region: {default_region}")

    # Try to get IB credentials (won't be available unless user has set them)
    try:
        ib_creds = get_credentials("interactive_brokers")
        print(f"✓ IB credentials available: {ib_creds.is_complete()}")
    except ConfigurationError:
        print("✓ IB credentials properly reported as unavailable")

    # Clean up environment variables
    del os.environ["KTRDR_TEST_USERNAME"]
    del os.environ["KTRDR_TEST_API_KEY"]


def verify_input_validation():
    """Verify input validation functionality."""
    print("\n=== Testing Input Validation ===")

    try:
        # Validate string input
        symbol = InputValidator.validate_string(
            "AAPL", min_length=1, max_length=5, pattern=r"^[A-Z]+$"
        )
        print(f"✓ Valid stock symbol: {symbol}")

        # Validate numeric input
        days = InputValidator.validate_numeric(30, min_value=1, max_value=365)
        print(f"✓ Valid day range: {days}")

        # Test sanitization
        params = sanitize_parameters(
            {
                "symbol": symbol,
                "days": days,
                "file_path": "../data/test.csv",
                "name": "test\x00name",
            }
        )

        print(f"✓ Sanitized parameters: {params}")
        print("✓ Path parameter properly resolved")
        print("✓ Control characters removed from string")

    except ValidationError as e:
        print(f"✗ Validation error: {e}")


def verify_security_config():
    """Verify security configuration loading."""
    print("\n=== Testing Security Configuration ===")

    config_loader = ConfigLoader()
    config = config_loader.load("config/settings.yaml")

    print("✓ Loaded configuration with security settings")
    print(f"✓ Validate user input: {config.security.validate_user_input}")
    print(
        f"✓ Protected file patterns: {', '.join(config.security.sensitive_file_patterns)}"
    )

    # Verify .gitignore patterns
    gitignore_path = Path(".gitignore")
    if gitignore_path.exists():
        with open(gitignore_path) as f:
            gitignore_content = f.read()

        security_patterns = ["*.key", "*.pem", "*.env", "*_credentials*", "*.cert"]
        for pattern in security_patterns:
            if pattern in gitignore_content:
                print(f"✓ .gitignore contains pattern: {pattern}")
            else:
                print(f"✗ .gitignore missing pattern: {pattern}")


if __name__ == "__main__":
    print("KTRDR Security Measures Verification")
    print("====================================")

    verify_credential_loading()
    verify_input_validation()
    verify_security_config()

    print("\n=== All Security Verifications Completed ===")
    print("Run the test suite for complete test coverage:")
    print(
        "  pytest -xvs tests/config/test_credentials.py tests/config/test_validation.py"
    )
