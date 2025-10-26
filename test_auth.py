#!/usr/bin/env python
"""Test script to verify authentication works"""
import requests
import json

BASE_URL = "http://localhost:8000"

# Test data
test_payload = {
    "name": "test-workflow",
    "definition": {
        "steps": [
            {
                "type": "HTTPS GET Request",
                "args": {"url": "https://example.com"}
            }
        ]
    }
}

print("Testing IA Suggestion endpoint...")
print("=" * 50)

# Test 1: Without Bearer prefix
print("\n1. Testing with token WITHOUT 'Bearer' prefix:")
print("   Header: Authorization: mock-test123")
response = requests.post(
    f"{BASE_URL}/ia/suggestion",
    headers={
        "Content-Type": "application/json",
        "Authorization": "mock-test123"
    },
    json=test_payload
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print("   ✓ SUCCESS!")
else:
    print(f"   ✗ FAILED: {response.json()}")

# Test 2: With Bearer prefix
print("\n2. Testing with token WITH 'Bearer' prefix:")
print("   Header: Authorization: Bearer mock-test123")
response = requests.post(
    f"{BASE_URL}/ia/suggestion",
    headers={
        "Content-Type": "application/json",
        "Authorization": "Bearer mock-test123"
    },
    json=test_payload
)
print(f"   Status: {response.status_code}")
if response.status_code == 200:
    print("   ✓ SUCCESS!")
    print(f"   Response: {json.dumps(response.json(), indent=2)}")
else:
    print(f"   ✗ FAILED: {response.json()}")

# Test 3: Invalid token
print("\n3. Testing with INVALID token:")
print("   Header: Authorization: invalid-token")
response = requests.post(
    f"{BASE_URL}/ia/suggestion",
    headers={
        "Content-Type": "application/json",
        "Authorization": "invalid-token"
    },
    json=test_payload
)
print(f"   Status: {response.status_code}")
if response.status_code == 401:
    print("   ✓ Correctly rejected!")
else:
    print(f"   ✗ Should have been rejected!")

print("\n" + "=" * 50)
print("Tests complete!")
