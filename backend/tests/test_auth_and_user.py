"""
Tests for Authentication and User endpoints:
- /api/auth/register
- /api/auth/login
- /api/auth/me
- /api/users/location
- /api/users/{user_id}
"""
import pytest
import requests
import time

class TestAuth:
    """Authentication flow tests"""
    
    def test_register_new_user(self, api_client, base_url):
        """Test user registration with unique email"""
        timestamp = int(time.time())
        response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Test User",
            "email": f"test_{timestamp}@example.com",
            "password": "testpass123"
        })
        assert response.status_code == 200, f"Registration failed: {response.text}"
        
        data = response.json()
        assert "token" in data, "Token missing in response"
        assert "user" in data, "User data missing in response"
        assert data["user"]["email"] == f"test_{timestamp}@example.com"
        assert data["user"]["name"] == "Test User"
        assert "id" in data["user"]
    
    def test_register_duplicate_email(self, api_client, base_url, test_user_credentials):
        """Test registration with existing email returns 400"""
        response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Duplicate",
            "email": test_user_credentials["email"],
            "password": "anypass"
        })
        assert response.status_code == 400, "Should reject duplicate email"
        data = response.json()
        assert "già registrata" in data.get("detail", "").lower()
    
    def test_login_success(self, api_client, base_url, test_user_credentials):
        """Test login with valid credentials"""
        response = api_client.post(f"{base_url}/api/auth/login", json=test_user_credentials)
        assert response.status_code == 200, f"Login failed: {response.text}"
        
        data = response.json()
        assert "token" in data, "Token missing"
        assert "user" in data, "User data missing"
        assert data["user"]["email"] == test_user_credentials["email"]
    
    def test_login_invalid_credentials(self, api_client, base_url):
        """Test login with wrong password"""
        response = api_client.post(f"{base_url}/api/auth/login", json={
            "email": "marco@demo.it",
            "password": "wrongpassword"
        })
        assert response.status_code == 401, "Should return 401 for invalid credentials"
    
    def test_get_current_user(self, api_client, base_url, test_user_credentials):
        """Test /api/auth/me with valid token"""
        # First login to get token
        login_response = api_client.post(f"{base_url}/api/auth/login", json=test_user_credentials)
        assert login_response.status_code == 200
        token = login_response.json()["token"]
        
        # Get current user
        response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200, f"/me failed: {response.text}"
        
        data = response.json()
        assert data["email"] == test_user_credentials["email"]
        assert "id" in data
        assert "name" in data
        assert "neighborhood" in data
    
    def test_get_current_user_no_token(self, api_client, base_url):
        """Test /api/auth/me without token returns 403"""
        response = api_client.get(f"{base_url}/api/auth/me")
        assert response.status_code == 403, "Should require authentication"


class TestUserEndpoints:
    """User profile and location tests"""
    
    def test_get_user_profile(self, api_client, base_url, test_user_credentials):
        """Test GET /api/users/{user_id}"""
        # Login to get user_id
        login_response = api_client.post(f"{base_url}/api/auth/login", json=test_user_credentials)
        user_id = login_response.json()["user"]["id"]
        
        # Get user profile (public endpoint, no auth needed)
        response = api_client.get(f"{base_url}/api/users/{user_id}")
        assert response.status_code == 200, f"Failed to get user: {response.text}"
        
        data = response.json()
        assert data["id"] == user_id
        assert data["name"] == "Marco Rossi"
        assert "listings_count" in data
        assert "sales_count" in data
        assert isinstance(data["listings_count"], int)
    
    def test_get_nonexistent_user(self, api_client, base_url):
        """Test GET user with invalid ID returns 404"""
        response = api_client.get(f"{base_url}/api/users/nonexistent-id-12345")
        assert response.status_code == 404
    
    def test_update_location(self, api_client, base_url):
        """Test PUT /api/users/location"""
        # Register new user for location test (to avoid 24h limit)
        timestamp = int(time.time())
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Location Tester",
            "email": f"location_{timestamp}@test.com",
            "password": "test123"
        })
        token = reg_response.json()["token"]
        
        # Update location
        response = api_client.put(
            f"{base_url}/api/users/location",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "latitude": 45.4642,
                "longitude": 9.1900,
                "neighborhood": "Milano Centro"
            }
        )
        assert response.status_code == 200, f"Location update failed: {response.text}"
        
        data = response.json()
        assert "message" in data
        assert data["neighborhood"] == "Milano Centro"
    
    def test_update_location_24h_limit(self, api_client, base_url, test_user_credentials):
        """Test location update respects 24h limit (may fail if not updated recently)"""
        login_response = api_client.post(f"{base_url}/api/auth/login", json=test_user_credentials)
        token = login_response.json()["token"]
        
        # Try to update twice in a row
        first_update = api_client.put(
            f"{base_url}/api/users/location",
            headers={"Authorization": f"Bearer {token}"},
            json={"latitude": 45.0, "longitude": 9.0, "neighborhood": "Test"}
        )
        
        # If first succeeds, second should fail
        if first_update.status_code == 200:
            second_update = api_client.put(
                f"{base_url}/api/users/location",
                headers={"Authorization": f"Bearer {token}"},
                json={"latitude": 46.0, "longitude": 10.0, "neighborhood": "Test2"}
            )
            assert second_update.status_code == 429, "Should enforce 24h limit"
        # If first fails with 429, limit is already active (test passes)
        elif first_update.status_code == 429:
            pytest.skip("24h limit already active for test user")
