#!/usr/bin/env python3
"""
Test script for Messaging & Calling SDK.

This script tests that the SDK can initialize properly with the test configuration.
"""

import asyncio
import sys
import os

# Add the messaging_sdk to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'messaging_sdk'))

async def test_sdk_initialization():
    """Test that the SDK can initialize properly."""
    print("🚀 Testing Messaging & Calling SDK initialization...")

    try:
        # Test config loading
        from messaging_sdk.core.config import settings
        print("✅ Configuration loaded successfully")

        # Validate configuration
        issues = settings.validate_configuration()
        if issues:
            print("⚠️  Configuration validation issues:")
            for issue in issues:
                print(f"   - {issue}")
        else:
            print("✅ Configuration validation passed")

        # Test email provider
        from messaging_sdk.providers.email import get_email_provider
        email_provider = get_email_provider()
        print(f"✅ Email provider initialized: {type(email_provider).__name__}")

        # Test cache provider
        from messaging_sdk.providers.cache import get_cache_provider
        cache_provider = get_cache_provider()
        print(f"✅ Cache provider initialized: {type(cache_provider).__name__}")

        # Test database connection (without creating tables)
        from messaging_sdk.database import engine
        print(f"✅ Database engine initialized: {engine.url}")

        # Test MessagingApp creation
        from messaging_sdk import MessagingApp
        app = MessagingApp(settings=settings)
        print("✅ MessagingApp created successfully")

        print("\n🎉 All tests passed! SDK is ready for development.")
        return True

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_sdk_initialization())
    sys.exit(0 if success else 1)