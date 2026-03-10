"""
Tests for Transactions and Chats:
- /api/transactions (POST - purchase)
- /api/transactions (GET - list)
- /api/chats (GET - list)
- /api/chats/{id} (GET - single)
- /api/chats/{id}/messages (POST - send message)
"""
import pytest
import requests
import time

class TestTransactions:
    """Transaction/Purchase flow tests"""
    
    def test_purchase_listing_creates_transaction_and_chat(self, api_client, base_url):
        """Test POST /api/transactions - full purchase flow with 5% commission"""
        # Create buyer and seller
        timestamp = int(time.time())
        
        # Seller
        seller_reg = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Seller User",
            "email": f"seller_tx_{timestamp}@test.com",
            "password": "test123"
        })
        seller_token = seller_reg.json()["token"]
        
        # Create listing
        listing_response = api_client.post(
            f"{base_url}/api/listings",
            headers={"Authorization": f"Bearer {seller_token}"},
            json={
                "title": "TEST_Item for Sale",
                "description": "Test item",
                "price": 100.0,
                "category": "Elettronica",
                "condition": "Buono",
                "images": []
            }
        )
        listing_id = listing_response.json()["id"]
        
        # Buyer
        buyer_reg = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Buyer User",
            "email": f"buyer_tx_{timestamp}@test.com",
            "password": "test123"
        })
        buyer_token = buyer_reg.json()["token"]
        
        # Purchase
        purchase_response = api_client.post(
            f"{base_url}/api/transactions",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"listing_id": listing_id}
        )
        assert purchase_response.status_code == 200, f"Purchase failed: {purchase_response.text}"
        
        data = purchase_response.json()
        assert "id" in data
        assert data["listing_id"] == listing_id
        assert data["price"] == 100.0
        assert data["commission"] == 5.0, "Commission should be 5% of 100"
        assert data["total"] == 105.0, "Total should be price + commission"
        assert data["status"] == "completed"
        assert "chat_id" in data
        
        # Verify transaction persists
        tx_list_response = api_client.get(
            f"{base_url}/api/transactions",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert tx_list_response.status_code == 200
        transactions = tx_list_response.json()
        assert len(transactions) > 0
        assert any(tx["id"] == data["id"] for tx in transactions)
        
        # Verify chat was created
        chat_id = data["chat_id"]
        chat_response = api_client.get(
            f"{base_url}/api/chats/{chat_id}",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        assert chat_response.status_code == 200
        chat_data = chat_response.json()
        assert chat_data["id"] == chat_id
        assert len(chat_data["messages"]) == 1  # System message
        assert "Acquisto completato" in chat_data["messages"][0]["text"]
    
    def test_purchase_own_listing_fails(self, api_client, base_url):
        """Test buying your own listing returns 400"""
        timestamp = int(time.time())
        reg_response = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Self Buyer",
            "email": f"selfbuy_{timestamp}@test.com",
            "password": "test123"
        })
        token = reg_response.json()["token"]
        
        # Create listing
        listing_response = api_client.post(
            f"{base_url}/api/listings",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "title": "TEST_Own Item",
                "description": "Test",
                "price": 50,
                "category": "Altro",
                "condition": "Buono",
                "images": []
            }
        )
        listing_id = listing_response.json()["id"]
        
        # Try to buy own listing
        purchase_response = api_client.post(
            f"{base_url}/api/transactions",
            headers={"Authorization": f"Bearer {token}"},
            json={"listing_id": listing_id}
        )
        assert purchase_response.status_code == 400
        assert "tuo annuncio" in purchase_response.json().get("detail", "").lower()
    
    def test_purchase_nonexistent_listing(self, api_client, base_url, test_user_credentials):
        """Test purchasing non-existent listing returns 404"""
        login_response = api_client.post(f"{base_url}/api/auth/login", json=test_user_credentials)
        token = login_response.json()["token"]
        
        response = api_client.post(
            f"{base_url}/api/transactions",
            headers={"Authorization": f"Bearer {token}"},
            json={"listing_id": "nonexistent-id-12345"}
        )
        assert response.status_code == 404
    
    def test_get_transactions(self, api_client, base_url, test_user_credentials):
        """Test GET /api/transactions returns user's transactions"""
        login_response = api_client.post(f"{base_url}/api/auth/login", json=test_user_credentials)
        token = login_response.json()["token"]
        
        response = api_client.get(
            f"{base_url}/api/transactions",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)


class TestChats:
    """Chat messaging tests"""
    
    def test_get_chats_list(self, api_client, base_url, test_user_credentials):
        """Test GET /api/chats returns user's chats"""
        login_response = api_client.post(f"{base_url}/api/auth/login", json=test_user_credentials)
        token = login_response.json()["token"]
        
        response = api_client.get(
            f"{base_url}/api/chats",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_send_message_in_chat(self, api_client, base_url):
        """Test POST /api/chats/{id}/messages - send message"""
        # Create full purchase flow to get chat
        timestamp = int(time.time())
        
        # Seller
        seller_reg = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Chat Seller",
            "email": f"chat_seller_{timestamp}@test.com",
            "password": "test123"
        })
        seller_token = seller_reg.json()["token"]
        
        listing_response = api_client.post(
            f"{base_url}/api/listings",
            headers={"Authorization": f"Bearer {seller_token}"},
            json={
                "title": "TEST_Chat Item",
                "description": "For chat test",
                "price": 50,
                "category": "Altro",
                "condition": "Buono",
                "images": []
            }
        )
        listing_id = listing_response.json()["id"]
        
        # Buyer
        buyer_reg = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Chat Buyer",
            "email": f"chat_buyer_{timestamp}@test.com",
            "password": "test123"
        })
        buyer_token = buyer_reg.json()["token"]
        
        # Purchase to create chat
        purchase_response = api_client.post(
            f"{base_url}/api/transactions",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"listing_id": listing_id}
        )
        chat_id = purchase_response.json()["chat_id"]
        
        # Send message as buyer
        message_response = api_client.post(
            f"{base_url}/api/chats/{chat_id}/messages",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"text": "Ciao, quando posso ritirare?"}
        )
        assert message_response.status_code == 200, f"Send message failed: {message_response.text}"
        
        msg_data = message_response.json()
        assert msg_data["text"] == "Ciao, quando posso ritirare?"
        assert "id" in msg_data
        assert "created_at" in msg_data
        
        # Verify message appears in chat
        chat_response = api_client.get(
            f"{base_url}/api/chats/{chat_id}",
            headers={"Authorization": f"Bearer {buyer_token}"}
        )
        chat_data = chat_response.json()
        assert len(chat_data["messages"]) == 2  # System + buyer message
        assert chat_data["messages"][-1]["text"] == "Ciao, quando posso ritirare?"
    
    def test_get_chat_unauthorized(self, api_client, base_url, test_user_credentials):
        """Test accessing chat you're not part of returns 403"""
        # Create a chat between two other users
        timestamp = int(time.time())
        
        seller_reg = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Private Seller",
            "email": f"private_seller_{timestamp}@test.com",
            "password": "test123"
        })
        seller_token = seller_reg.json()["token"]
        
        listing_response = api_client.post(
            f"{base_url}/api/listings",
            headers={"Authorization": f"Bearer {seller_token}"},
            json={
                "title": "TEST_Private Item",
                "description": "Test",
                "price": 30,
                "category": "Altro",
                "condition": "Buono",
                "images": []
            }
        )
        listing_id = listing_response.json()["id"]
        
        buyer_reg = api_client.post(f"{base_url}/api/auth/register", json={
            "name": "Private Buyer",
            "email": f"private_buyer_{timestamp}@test.com",
            "password": "test123"
        })
        buyer_token = buyer_reg.json()["token"]
        
        purchase_response = api_client.post(
            f"{base_url}/api/transactions",
            headers={"Authorization": f"Bearer {buyer_token}"},
            json={"listing_id": listing_id}
        )
        chat_id = purchase_response.json()["chat_id"]
        
        # Try to access as third user (Marco)
        marco_login = api_client.post(f"{base_url}/api/auth/login", json=test_user_credentials)
        marco_token = marco_login.json()["token"]
        
        response = api_client.get(
            f"{base_url}/api/chats/{chat_id}",
            headers={"Authorization": f"Bearer {marco_token}"}
        )
        assert response.status_code == 403
    
    def test_get_nonexistent_chat(self, api_client, base_url, test_user_credentials):
        """Test getting non-existent chat returns 404"""
        login_response = api_client.post(f"{base_url}/api/auth/login", json=test_user_credentials)
        token = login_response.json()["token"]
        
        response = api_client.get(
            f"{base_url}/api/chats/nonexistent-chat-id",
            headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 404
