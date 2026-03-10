"""
Tests for Admin panel and Legal compliance features:
- /api/auth/register (with accepted_privacy and accepted_rules validation)
- /api/admin/users (admin only)
- /api/admin/users/{id} DELETE (admin only)
- /api/admin-panel (HTML panel)
- /api/admin/seed (create admin account)
"""
import pytest
import requests
import time
import os

class TestRegistrationLegalCompliance:
    """Test registration requires privacy and rules acceptance"""
    
    def test_register_without_privacy_acceptance_fails(self, api_client, base_url):
        """Registration MUST fail without accepted_privacy=true"""
        timestamp = int(time.time())
        response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Test User",
            "email": f"test_no_privacy_{timestamp}@example.com",
            "password": "testpass123",
            "regione": "Lazio",
            "provincia": "Roma",
            "accepted_privacy": False,
            "accepted_rules": True
        })
        assert response.status_code == 400, f"Should reject without privacy acceptance, got {response.status_code}: {response.text}"
        data = response.json()
        assert "privacy" in data.get("detail", "").lower() or "accettare" in data.get("detail", "").lower()
    
    def test_register_without_rules_acceptance_fails(self, api_client, base_url):
        """Registration MUST fail without accepted_rules=true"""
        timestamp = int(time.time())
        response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Test User",
            "email": f"test_no_rules_{timestamp}@example.com",
            "password": "testpass123",
            "regione": "Lazio",
            "provincia": "Roma",
            "accepted_privacy": True,
            "accepted_rules": False
        })
        assert response.status_code == 400, f"Should reject without rules acceptance, got {response.status_code}: {response.text}"
        data = response.json()
        assert "regole" in data.get("detail", "").lower() or "accettare" in data.get("detail", "").lower()
    
    def test_register_without_both_acceptances_fails(self, api_client, base_url):
        """Registration MUST fail without both privacy and rules"""
        timestamp = int(time.time())
        response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Test User",
            "email": f"test_no_legal_{timestamp}@example.com",
            "password": "testpass123",
            "regione": "Lazio",
            "provincia": "Roma",
            "accepted_privacy": False,
            "accepted_rules": False
        })
        assert response.status_code == 400, "Should reject without legal acceptances"
    
    def test_register_with_both_acceptances_succeeds(self, api_client, base_url):
        """Registration succeeds with accepted_privacy=true and accepted_rules=true"""
        timestamp = int(time.time())
        response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Legal User",
            "email": f"test_legal_{timestamp}@example.com",
            "password": "testpass123",
            "regione": "Lombardia",
            "provincia": "Milano",
            "accepted_privacy": True,
            "accepted_rules": True
        })
        assert response.status_code == 200, f"Registration should succeed with legal acceptances: {response.text}"
        
        data = response.json()
        assert "token" in data, "Token missing"
        assert "user" in data, "User data missing"
        assert data["user"]["email"] == f"test_legal_{timestamp}@example.com"
        
        # Verify user was created with accepted timestamps
        user_id = data["user"]["id"]
        token = data["token"]
        me_response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200


class TestAdminEndpoints:
    """Test admin-only endpoints"""
    
    def test_admin_seed_creates_admin_user(self, api_client, base_url):
        """POST /api/admin/seed creates admin account"""
        response = api_client.post(f"{base_url}/api/admin/seed")
        assert response.status_code == 200, f"Admin seed failed: {response.text}"
        
        data = response.json()
        assert "email" in data
        assert data["email"] == os.environ.get('ADMIN_EMAIL', 'admin@scm.it')
    
    def test_admin_login_success(self, api_client, base_url):
        """Admin can login with credentials"""
        # Ensure admin exists
        api_client.post(f"{base_url}/api/admin/seed")
        
        # Login as admin
        response = api_client.post(f"{base_url}/api/auth/login", json={
            "email": "admin@scm.it",
            "password": "admin2024!"
        })
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        
        data = response.json()
        assert "token" in data
        
        # Verify role is admin
        token = data["token"]
        me_response = api_client.get(
            f"{base_url}/api/auth/me",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert me_response.status_code == 200
        me_data = me_response.json()
        assert me_data.get("role") == "admin", "Admin user should have role=admin"
    
    def test_get_admin_users_requires_admin_token(self, api_client, base_url):
        """GET /api/admin/users requires admin authentication"""
        # Try without token
        response = api_client.get(f"{base_url}/api/admin/users")
        assert response.status_code == 403, "Should require authentication"
        
        # Try with regular user token
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Regular User",
            "email": f"regular_{int(time.time())}@test.com",
            "password": "test123",
            "regione": "Lazio",
            "provincia": "Roma",
            "accepted_privacy": True,
            "accepted_rules": True
        })
        regular_token = reg_response.json()["token"]
        
        response = api_client.get(
            f"{base_url}/api/admin/users",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        assert response.status_code == 403, "Regular user should not access admin endpoint"
    
    def test_get_admin_users_success(self, api_client, base_url):
        """Admin can list all users with GET /api/admin/users"""
        # Ensure admin exists and login
        api_client.post(f"{base_url}/api/admin/seed")
        login_response = api_client.post(f"{base_url}/api/auth/login", json={
            "email": "admin@scm.it",
            "password": "admin2024!"
        })
        admin_token = login_response.json()["token"]
        
        # Get users list
        response = api_client.get(
            f"{base_url}/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 200, f"Failed to get users: {response.text}"
        
        users = response.json()
        assert isinstance(users, list), "Should return list of users"
        
        # Verify user structure includes listings and purchases counts
        if len(users) > 0:
            user = users[0]
            assert "id" in user
            assert "name" in user
            assert "email" in user
            assert "listings_count" in user
            assert "purchases_count" in user
            assert isinstance(user["listings_count"], int)
            assert isinstance(user["purchases_count"], int)
    
    def test_delete_admin_user_requires_admin(self, api_client, base_url):
        """DELETE /api/admin/users/{id} requires admin token"""
        # Create a test user to delete
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "To Delete",
            "email": f"todelete_{int(time.time())}@test.com",
            "password": "test123",
            "regione": "Lazio",
            "provincia": "Roma",
            "accepted_privacy": True,
            "accepted_rules": True
        })
        user_id = reg_response.json()["user"]["id"]
        regular_token = reg_response.json()["token"]
        
        # Try to delete with regular user token
        response = api_client.delete(
            f"{base_url}/api/admin/users/{user_id}",
            headers={"Authorization": f"Bearer {regular_token}"}
        )
        assert response.status_code == 403, "Regular user cannot delete users"
    
    def test_delete_admin_user_success(self, api_client, base_url):
        """Admin can delete users with DELETE /api/admin/users/{id}"""
        # Create admin and login
        api_client.post(f"{base_url}/api/admin/seed")
        login_response = api_client.post(f"{base_url}/api/auth/login", json={
            "email": "admin@scm.it",
            "password": "admin2024!"
        })
        admin_token = login_response.json()["token"]
        
        # Create a test user to delete
        timestamp = int(time.time())
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "TEST_DeleteMe",
            "email": f"TEST_deleteme_{timestamp}@test.com",
            "password": "test123",
            "regione": "Lazio",
            "provincia": "Roma",
            "accepted_privacy": True,
            "accepted_rules": True
        })
        user_id = reg_response.json()["user"]["id"]
        user_email = reg_response.json()["user"]["email"]
        
        # Delete user as admin
        delete_response = api_client.delete(
            f"{base_url}/api/admin/users/{user_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert delete_response.status_code == 200, f"Failed to delete user: {delete_response.text}"
        
        data = delete_response.json()
        assert "message" in data
        
        # Verify user is deleted by trying to get profile
        profile_response = api_client.get(f"{base_url}/api/users/{user_id}")
        assert profile_response.status_code == 404, "User should be deleted"
    
    def test_cannot_delete_admin_user(self, api_client, base_url):
        """Admin cannot delete another admin user"""
        # Create admin and login
        api_client.post(f"{base_url}/api/admin/seed")
        login_response = api_client.post(f"{base_url}/api/auth/login", json={
            "email": "admin@scm.it",
            "password": "admin2024!"
        })
        admin_token = login_response.json()["token"]
        admin_id = login_response.json()["user"]["id"]
        
        # Try to delete admin user
        response = api_client.delete(
            f"{base_url}/api/admin/users/{admin_id}",
            headers={"Authorization": f"Bearer {admin_token}"}
        )
        assert response.status_code == 400, "Should not allow deleting admin users"


class TestAdminPanelHTML:
    """Test web-based admin panel"""
    
    def test_admin_panel_html_accessible(self, api_client, base_url):
        """GET /api/admin-panel returns HTML page"""
        response = api_client.get(f"{base_url}/api/admin-panel")
        assert response.status_code == 200, f"Admin panel not accessible: {response.status_code}"
        
        # Verify it's HTML
        content_type = response.headers.get('content-type', '')
        assert 'html' in content_type.lower(), f"Should return HTML, got {content_type}"
        
        # Verify HTML contains key elements
        html = response.text
        assert 'Admin Panel' in html, "Should contain 'Admin Panel' title"
        assert 'Second Chance Market' in html, "Should contain app name"
        assert 'Email' in html or 'email' in html, "Should have email input"
        assert 'Password' in html or 'password' in html, "Should have password input"
        assert 'doLogin' in html, "Should have login function"
