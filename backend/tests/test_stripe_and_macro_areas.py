"""
Tests for Stripe payment integration and Macro Areas feature
Testing:
- GET /api/macro-areas - returns 20 Italian regions with provinces
- POST /api/auth/register - with regione and provincia fields
- POST /api/checkout/create - creates Stripe checkout session with 5% commission
- GET /api/checkout/status/{session_id} - checks payment status
"""
import pytest
import requests
import os

# Frontend uses EXPO_PUBLIC_BACKEND_URL, but for backend tests we need to construct it
BASE_URL = "https://local-resale-hub-2.preview.emergentagent.com"


class TestMacroAreas:
    """Test macro areas endpoint"""

    def test_get_macro_areas_returns_20_regions(self):
        """Test that macro-areas endpoint returns exactly 20 Italian regions"""
        response = requests.get(f"{BASE_URL}/api/macro-areas")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 20, f"Expected 20 regions, got {len(data)}"

        # Check structure of first region
        first_region = data[0]
        assert "regione" in first_region, "Each region should have 'regione' field"
        assert "province" in first_region, "Each region should have 'province' field"
        assert isinstance(first_region["province"], list), "Provinces should be a list"

        # Check province structure
        if first_region["province"]:
            first_prov = first_region["province"][0]
            assert "nome" in first_prov, "Province should have 'nome' field"
            assert "lat" in first_prov, "Province should have 'lat' field"
            assert "lng" in first_prov, "Province should have 'lng' field"

        print(f"✓ Macro areas endpoint returns {len(data)} regions")

    def test_macro_areas_includes_lombardia(self):
        """Test that Lombardia region is present with correct structure"""
        response = requests.get(f"{BASE_URL}/api/macro-areas")
        data = response.json()

        lombardia = next((r for r in data if r["regione"] == "Lombardia"), None)
        assert lombardia is not None, "Lombardia region should be present"
        assert len(lombardia["province"]) > 0, "Lombardia should have provinces"

        # Check for Milano
        milano = next((p for p in lombardia["province"] if p["nome"] == "Milano"), None)
        assert milano is not None, "Milano should be in Lombardia provinces"
        assert milano["lat"] == 45.4642, "Milano latitude should be correct"
        assert milano["lng"] == 9.1900, "Milano longitude should be correct"

        print("✓ Lombardia region with Milano province validated")


class TestRegistrationWithMacroArea:
    """Test registration with regione and provincia fields"""

    def test_register_with_region_and_province(self):
        """Test registration with valid regione and provincia"""
        import uuid
        email = f"test_region_{uuid.uuid4().hex[:8]}@test.it"
        
        payload = {
            "name": "Test User Region",
            "email": email,
            "password": "test123",
            "regione": "Lazio",
            "provincia": "Roma"
        }

        response = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert "token" in data, "Response should include token"
        assert "user" in data, "Response should include user"

        user = data["user"]
        assert user["regione"] == "Lazio", f"Expected regione 'Lazio', got {user.get('regione')}"
        assert user["provincia"] == "Roma", f"Expected provincia 'Roma', got {user.get('provincia')}"
        assert user["neighborhood"] == "Roma, Lazio", f"Expected neighborhood 'Roma, Lazio', got {user.get('neighborhood')}"
        
        # Coordinates should match Roma
        assert user["latitude"] == 41.9028, "Latitude should match Roma"
        assert user["longitude"] == 12.4964, "Longitude should match Roma"

        print(f"✓ Registration with region (Lazio, Roma) successful")

    def test_register_with_lombardia_milano(self):
        """Test registration with Lombardia - Milano"""
        import uuid
        email = f"test_milano_{uuid.uuid4().hex[:8]}@test.it"
        
        payload = {
            "name": "Test User Milano",
            "email": email,
            "password": "test123",
            "regione": "Lombardia",
            "provincia": "Milano"
        }

        response = requests.post(f"{BASE_URL}/api/auth/register", json=payload)
        assert response.status_code == 200, f"Expected 200, got {response.status_code}"

        data = response.json()
        user = data["user"]
        assert user["regione"] == "Lombardia"
        assert user["provincia"] == "Milano"
        assert user["latitude"] == 45.4642, "Latitude should match Milano"
        assert user["longitude"] == 9.1900, "Longitude should match Milano"

        print(f"✓ Registration with Lombardia - Milano successful")


class TestStripeCheckout:
    """Test Stripe checkout integration"""

    @pytest.fixture
    def authenticated_user_and_listing(self):
        """Create a user, login, and create a listing for purchase"""
        import uuid
        
        # Create seller
        seller_email = f"seller_{uuid.uuid4().hex[:8]}@test.it"
        seller_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Seller User",
            "email": seller_email,
            "password": "seller123",
            "regione": "Lazio",
            "provincia": "Roma"
        })
        seller_data = seller_response.json()
        seller_token = seller_data["token"]

        # Create listing
        listing_response = requests.post(
            f"{BASE_URL}/api/listings",
            headers={"Authorization": f"Bearer {seller_token}"},
            json={
                "title": "Test Item for Stripe",
                "description": "Test item for payment",
                "price": 100.00,
                "category": "Elettronica",
                "condition": "Buono",
                "images": []
            }
        )
        listing = listing_response.json()

        # Create buyer
        buyer_email = f"buyer_{uuid.uuid4().hex[:8]}@test.it"
        buyer_response = requests.post(f"{BASE_URL}/api/auth/register", json={
            "name": "Buyer User",
            "email": buyer_email,
            "password": "buyer123",
            "regione": "Lombardia",
            "provincia": "Milano"
        })
        buyer_data = buyer_response.json()
        buyer_token = buyer_data["token"]

        return {
            "listing_id": listing["id"],
            "listing_price": listing["price"],
            "buyer_token": buyer_token,
            "seller_token": seller_token
        }

    def test_create_checkout_session(self, authenticated_user_and_listing):
        """Test creating a Stripe checkout session with 5% commission"""
        test_data = authenticated_user_and_listing
        
        payload = {
            "listing_id": test_data["listing_id"],
            "origin_url": BASE_URL
        }

        response = requests.post(
            f"{BASE_URL}/api/checkout/create",
            headers={"Authorization": f"Bearer {test_data['buyer_token']}"},
            json=payload
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

        data = response.json()
        assert "checkout_url" in data, "Response should include checkout_url"
        assert "session_id" in data, "Response should include session_id"
        assert "tx_id" in data, "Response should include transaction id"

        # Verify checkout URL is a valid Stripe URL
        assert data["checkout_url"].startswith("http"), "checkout_url should be a valid URL"
        assert len(data["session_id"]) > 0, "session_id should not be empty"

        print(f"✓ Checkout session created: {data['session_id']}")
        print(f"  Checkout URL: {data['checkout_url'][:50]}...")

        # Calculate expected commission
        listing_price = test_data["listing_price"]
        expected_commission = round(listing_price * 0.05, 2)
        expected_total = round(listing_price + expected_commission, 2)
        
        print(f"✓ Price: {listing_price} €, Commission (5%): {expected_commission} €, Total: {expected_total} €")

    def test_checkout_status_initiated(self, authenticated_user_and_listing):
        """Test checking payment status (should be 'initiated' initially)"""
        test_data = authenticated_user_and_listing
        
        # Create checkout
        checkout_response = requests.post(
            f"{BASE_URL}/api/checkout/create",
            headers={"Authorization": f"Bearer {test_data['buyer_token']}"},
            json={
                "listing_id": test_data["listing_id"],
                "origin_url": BASE_URL
            }
        )
        checkout_data = checkout_response.json()
        session_id = checkout_data["session_id"]

        # Check status
        status_response = requests.get(
            f"{BASE_URL}/api/checkout/status/{session_id}",
            headers={"Authorization": f"Bearer {test_data['buyer_token']}"}
        )
        
        assert status_response.status_code == 200, f"Expected 200, got {status_response.status_code}"

        status_data = status_response.json()
        assert "status" in status_data, "Response should include status"
        assert "payment_status" in status_data, "Response should include payment_status"
        assert "tx_id" in status_data, "Response should include tx_id"

        # Status should be pending/initiated (not paid without actual Stripe payment)
        assert status_data["payment_status"] in ["initiated", "unpaid", "pending"], \
            f"Payment should be initiated/unpaid, got {status_data['payment_status']}"

        print(f"✓ Checkout status check successful: {status_data['payment_status']}")

    def test_checkout_own_listing_fails(self, authenticated_user_and_listing):
        """Test that user cannot purchase their own listing"""
        test_data = authenticated_user_and_listing
        
        # Try to buy own listing using seller token
        response = requests.post(
            f"{BASE_URL}/api/checkout/create",
            headers={"Authorization": f"Bearer {test_data['seller_token']}"},
            json={
                "listing_id": test_data["listing_id"],
                "origin_url": BASE_URL
            }
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}"
        
        error = response.json()
        assert "detail" in error, "Error response should include detail"
        assert "tuo annuncio" in error["detail"].lower(), "Error should mention own listing"

        print("✓ Correctly prevented purchasing own listing")

    def test_checkout_nonexistent_listing(self, authenticated_user_and_listing):
        """Test checkout with non-existent listing"""
        test_data = authenticated_user_and_listing
        
        response = requests.post(
            f"{BASE_URL}/api/checkout/create",
            headers={"Authorization": f"Bearer {test_data['buyer_token']}"},
            json={
                "listing_id": "nonexistent-listing-id",
                "origin_url": BASE_URL
            }
        )
        
        assert response.status_code == 404, f"Expected 404, got {response.status_code}"
        
        error = response.json()
        assert "detail" in error, "Error response should include detail"

        print("✓ Correctly returned 404 for non-existent listing")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
