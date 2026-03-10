import pytest
import requests
import os

@pytest.fixture(scope="session")
def base_url():
    url = os.environ.get('EXPO_PUBLIC_BACKEND_URL')
    if not url:
        pytest.fail("EXPO_PUBLIC_BACKEND_URL not set in environment")
    return url.rstrip('/')

@pytest.fixture(scope="session")
def api_client():
    """Shared requests session for all tests"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session

@pytest.fixture(scope="session")
def test_user_credentials():
    """Demo user credentials from seed data"""
    return {
        "email": "marco@demo.it",
        "password": "demo123"
    }

@pytest.fixture(scope="session")
def demo_seller2_credentials():
    """Second demo user credentials"""
    return {
        "email": "giulia@demo.it",
        "password": "demo123"
    }
