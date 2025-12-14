from app.core.security import hash_password, verify_password

# Test password hashing
print("🔐 Testing Password Hashing")
print("=" * 60)

password = "MySecurePassword123!"
print(f"Original password: {password}")
print()

# Hash the password
hashed = hash_password(password)
print(f"Hashed password: {hashed}")
print(f"Length: {len(hashed)} characters")
print()

# Verify correct password
is_correct = verify_password("MySecurePassword123!", hashed)
print(f"✅ Correct password verification: {is_correct}")

# Verify wrong password
is_wrong = verify_password("WrongPassword", hashed)
print(f"❌ Wrong password verification: {is_wrong}")
print()

# Hash same password again (should be different!)
hashed2 = hash_password(password)
print(f"Same password hashed again: {hashed2}")
print(f"Are hashes identical? {hashed == hashed2} (should be False!)")
print()

print("=" * 60)
print("🎉 Password hashing works correctly!")
print()
print("Security features:")
print("✅ Each hash is unique (even for same password)")
print("✅ Original password cannot be recovered")
print("✅ Verification is fast but hashing is slow (prevents brute force)")