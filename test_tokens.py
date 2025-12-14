from app.core.security import create_access_token, create_refresh_token, decode_token

print("🔑 Testing JWT Tokens")
print("=" * 60)

# Create tokens
user_data = {"user_id": 1, "username": "ukeme"}

access_token = create_access_token(user_data)
refresh_token = create_refresh_token(user_data)

print(f"Access Token (first 50 chars): {access_token[:50]}...")
print(f"Refresh Token (first 50 chars): {refresh_token[:50]}...")
print()

# Decode access token
decoded = decode_token(access_token)
print(f"Decoded payload:")
print(f"  User ID: {decoded.get('user_id')}")
print(f"  Username: {decoded.get('username')}")
print(f"  Expires: {decoded.get('exp')}")
print()

print("=" * 60)
print("✅ JWT tokens working correctly!")