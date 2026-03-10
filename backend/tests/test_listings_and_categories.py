"""
Tests for Listings and Categories:
- /api/listings (GET with filters)
- /api/listings/{id} (GET)
- /api/listings (POST - create)
- /api/listings/{id} (PUT - update)
- /api/listings/{id} (DELETE)
- /api/categories (GET)
"""
import pytest
import requests
import time

class TestCategories:
    """Category endpoint tests"""
    
    def test_get_categories(self, api_client, base_url):
        """Test GET /api/categories returns all 6 categories with counts"""
        response = api_client.get(f"{base_url}/api/categories")
        assert response.status_code == 200, f"Categories failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return list"
        assert len(data) == 6, "Should have 6 categories"
        
        # Check structure
        for cat in data:
            assert "name" in cat
            assert "count" in cat
            assert isinstance(cat["count"], int)
        
        # Check expected categories
        cat_names = [c["name"] for c in data]
        expected = ["Elettronica", "Abbigliamento", "Casa & Arredamento", 
                    "Sport & Tempo Libero", "Libri & Media", "Altro"]
        for exp in expected:
            assert exp in cat_names, f"Missing category: {exp}"


class TestListings:
    """Listing CRUD and filtering tests"""
    
    def test_get_all_listings(self, api_client, base_url):
        """Test GET /api/listings returns seeded data"""
        response = api_client.get(f"{base_url}/api/listings")
        assert response.status_code == 200, f"Get listings failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list), "Should return list"
        assert len(data) == 12, "Should have 12 seeded listings"
        
        # Check listing structure
        listing = data[0]
        assert "id" in listing
        assert "title" in listing
        assert "price" in listing
        assert "category" in listing
        assert "condition" in listing
        assert "seller_name" in listing
        assert "seller_neighborhood" in listing
        assert "status" in listing
        assert listing["status"] == "active"
    
    def test_get_listings_with_category_filter(self, api_client, base_url):
        """Test GET /api/listings?category=Elettronica"""
        response = api_client.get(f"{base_url}/api/listings?category=Elettronica")
        assert response.status_code == 200, f"Category filter failed: {response.text}"
        
        data = response.json()
        assert isinstance(data, list)
        # All returned items should be Elettronica
        for listing in data:
            assert listing["category"] == "Elettronica"
    
    def test_get_listings_with_search(self, api_client, base_url):
        """Test GET /api/listings?search=iPhone"""
        response = api_client.get(f"{base_url}/api/listings?search=iPhone")
        assert response.status_code == 200
        
        data = response.json()
        assert len(data) > 0, "Should find iPhone in seeded data"
        # Check if search term appears in title or description
        found = False
        for listing in data:
            if "iphone" in listing["title"].lower() or "iphone" in listing["description"].lower():
                found = True
                break
        assert found, "Search should match title or description"
    
    def test_get_listings_with_price_filter(self, api_client, base_url):
        """Test GET /api/listings?min_price=100&max_price=500"""
        response = api_client.get(f"{base_url}/api/listings?min_price=100&max_price=500")
        assert response.status_code == 200
        
        data = response.json()
        for listing in data:
            assert 100 <= listing["price"] <= 500
    
    def test_get_single_listing(self, api_client, base_url):
        """Test GET /api/listings/{id}"""
        # First get all listings to get an ID
        all_listings = api_client.get(f"{base_url}/api/listings").json()
        listing_id = all_listings[0]["id"]
        
        response = api_client.get(f"{base_url}/api/listings/{listing_id}")
        assert response.status_code == 200
        
        data = response.json()
        assert data["id"] == listing_id
        assert "title" in data
        assert "description" in data
    
    def test_get_nonexistent_listing(self, api_client, base_url):
        """Test GET listing with invalid ID returns 404"""
        response = api_client.get(f"{base_url}/api/listings/nonexistent-id-99999")
        assert response.status_code == 404
    
    def test_create_listing(self, api_client, base_url):
        """Test POST /api/listings - create new listing"""
        # Register and login
        timestamp = int(time.time())
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Seller Test",
            "email": f"seller_{timestamp}@test.com",
            "password": "test123"
        })
        token = reg_response.json()["token"]
        
        # Create listing
        response = api_client.post(
            f"{base_url}/api/listings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST_Laptop Gaming",
                "description": "High performance gaming laptop",
                "price": 899.99,
                "category": "Elettronica",
                "condition": "Come nuovo",
                "images": []
            }
        )
        assert response.status_code == 200, f"Create listing failed: {response.text}"
        
        data = response.json()
        assert data["title"] == "TEST_Laptop Gaming"
        assert data["price"] == 899.99
        assert data["category"] == "Elettronica"
        assert "id" in data
        
        # Verify by GET
        listing_id = data["id"]
        get_response = api_client.get(f"{base_url}/api/listings/{listing_id}")
        assert get_response.status_code == 200
        assert get_response.json()["title"] == "TEST_Laptop Gaming"
    
    def test_create_listing_invalid_category(self, api_client, base_url, test_user_credentials):
        """Test creating listing with invalid category returns 400"""
        login_response = api_client.post(f"{base_url}/api/auth/login", json=test_user_credentials)
        token = login_response.json()["token"]
        
        response = api_client.post(
            f"{base_url}/api/listings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "Test",
                "description": "Test",
                "price": 10,
                "category": "InvalidCategory",
                "condition": "Buono",
                "images": []
            }
        )
        assert response.status_code == 400
        assert "categoria" in response.json().get("detail", "").lower()
    
    def test_update_own_listing(self, api_client, base_url):
        """Test PUT /api/listings/{id} - update own listing"""
        # Create user and listing first
        timestamp = int(time.time())
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Updater",
            "email": f"updater_{timestamp}@test.com",
            "password": "test123"
        })
        token = reg_response.json()["token"]
        
        # Create listing
        create_response = api_client.post(
            f"{base_url}/api/listings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST_Original Title",
                "description": "Original",
                "price": 50,
                "category": "Altro",
                "condition": "Buono",
                "images": []
            }
        )
        listing_id = create_response.json()["id"]
        
        # Update listing
        update_response = api_client.put(
            f"{base_url}/api/listings/{listing_id}",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "TEST_Updated Title", "price": 75}
        )
        assert update_response.status_code == 200
        
        data = update_response.json()
        assert data["title"] == "TEST_Updated Title"
        assert data["price"] == 75
    
    def test_update_others_listing_forbidden(self, api_client, base_url, test_user_credentials):
        """Test updating another user's listing returns 403"""
        # Get Marco's listing
        all_listings = api_client.get(f"{base_url}/api/listings").json()
        marco_listing = next(l for l in all_listings if l["seller_name"] == "Marco Rossi")
        
        # Login as Giulia
        login_response = api_client.post(f"{base_url}/api/auth/login", json={
            "email": "giulia@demo.it",
            "password": "demo123"
        })
        token = login_response.json()["token"]
        
        # Try to update Marco's listing
        response = api_client.put(
            f"{base_url}/api/listings/{marco_listing['id']}",
            headers={"Authorization": f"Bearer {token}"},
            json={"title": "Hacked"}
        )
        assert response.status_code == 403
    
    def test_delete_own_listing(self, api_client, base_url):
        """Test DELETE /api/listings/{id}"""
        # Create user and listing
        timestamp = int(time.time())
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Deleter",
            "email": f"deleter_{timestamp}@test.com",
            "password": "test123"
        })
        token = reg_response.json()["token"]
        
        create_response = api_client.post(
            f"{base_url}/api/listings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST_To Delete",
                "description": "Will be deleted",
                "price": 10,
                "category": "Altro",
                "condition": "Buono",
                "images": []
            }
        )
        listing_id = create_response.json()["id"]
        
        # Delete
        delete_response = api_client.delete(
            f"{base_url}/api/listings/{listing_id}",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert delete_response.status_code == 200
        
        # Verify deleted
        get_response = api_client.get(f"{base_url}/api/listings/{listing_id}")
        assert get_response.status_code == 404
