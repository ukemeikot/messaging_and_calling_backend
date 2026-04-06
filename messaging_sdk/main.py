"""
Main application file for the Messaging & Calling SDK.

This demonstrates how to use the SDK to create a messaging application.
For production use, create your own main.py file.
"""

from messaging_sdk import MessagingApp
from messaging_sdk.core.config import settings

# Validate configuration
issues = settings.validate_configuration()
if issues:
    print("❌ Configuration issues found:")
    for issue in issues:
        print(f"   - {issue}")
    print("\nPlease check your .env file and fix the issues above.")
    exit(1)

# Create the application using the SDK
app = MessagingApp(settings=settings)

# Add any custom routes or middleware here if needed
# app.include_router(your_custom_router)

print("✅ Messaging & Calling API initialized successfully!")
print(f"📚 API Documentation: http://localhost:8000/docs")
print(f"🔍 ReDoc: http://localhost:8000/redoc")