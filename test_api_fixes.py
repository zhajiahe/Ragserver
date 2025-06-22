#!/usr/bin/env python3
"""Test API fixes, especially 204 response."""

import asyncio
import sys
import traceback
from fastapi import FastAPI
from fastapi.testclient import TestClient
from ragbackend.api.collections import router as collections_router
from ragbackend.database.connection import init_db_pool, init_database_tables, close_db_pool


async def init_test_db():
    """Initialize test database."""
    await init_db_pool()
    await init_database_tables()


def create_test_app():
    """Create a test FastAPI app without lifespan."""
    app = FastAPI()
    app.include_router(collections_router, tags=["Collections"])
    return app


def test_204_response():
    """Test that delete operations return proper 204 response."""
    print("🔍 Testing API 204 response...")
    
    app = create_test_app()
    client = TestClient(app)
    
    try:
        # Create a collection first
        create_response = client.post("/collections/", json={
            "name": "Test Delete Collection",
            "description": "This will be deleted",
            "embedding_model": "bge-m3",
            "embedding_provider": "ollama"
        })
        
        if create_response.status_code != 201:
            print(f"❌ Failed to create collection: {create_response.status_code}")
            print(f"Response: {create_response.text}")
            return False
            
        collection_id = create_response.json()["id"]
        print(f"✅ Collection created: {collection_id}")
        
        # Test delete with proper 204 response
        delete_response = client.delete(f"/collections/{collection_id}")
        
        # Check status code
        if delete_response.status_code != 204:
            print(f"❌ Expected 204, got {delete_response.status_code}")
            print(f"Response: {delete_response.text}")
            return False
        
        # Check that content is empty (204 should have no content)
        if delete_response.content:
            print(f"❌ 204 response should have no content, got: {delete_response.content}")
            return False
            
        print("✅ Delete operation returns proper 204 response")
        
        # Verify collection was actually deleted
        get_response = client.get(f"/collections/{collection_id}")
        if get_response.status_code != 404:
            print(f"❌ Collection should be deleted, got status: {get_response.status_code}")
            return False
            
        print("✅ Collection was properly deleted")
        return True
        
    except Exception as e:
        print(f"❌ API test failed: {e}")
        traceback.print_exc()
        return False


def test_api_response_consistency():
    """Test API response consistency."""
    print("\n🔍 Testing API response consistency...")
    
    app = create_test_app()
    client = TestClient(app)
    
    try:
        # Create a collection
        create_response = client.post("/collections/", json={
            "name": "Test API Collection",
            "description": "Test description",
            "embedding_model": "bge-m3",
            "embedding_provider": "ollama"
        })
        
        if create_response.status_code != 201:
            print(f"❌ Failed to create collection: {create_response.status_code}")
            print(f"Response: {create_response.text}")
            return False
            
        collection_data = create_response.json()
        collection_id = collection_data["id"]
        
        # Check create response has all fields
        required_fields = ['id', 'name', 'description', 'embedding_model', 'embedding_provider', 'created_at', 'updated_at']
        missing_fields = [field for field in required_fields if field not in collection_data]
        
        if missing_fields:
            print(f"❌ Create response missing fields: {missing_fields}")
            return False
        
        print("✅ Create response has all required fields")
        
        # Test get single collection
        get_response = client.get(f"/collections/{collection_id}")
        if get_response.status_code != 200:
            print(f"❌ Failed to get collection: {get_response.status_code}")
            print(f"Response: {get_response.text}")
            return False
            
        get_data = get_response.json()
        missing_fields = [field for field in required_fields if field not in get_data]
        
        if missing_fields:
            print(f"❌ Get response missing fields: {missing_fields}")
            return False
            
        print("✅ Get single collection has all required fields")
        
        # Test get all collections
        list_response = client.get("/collections/")
        if list_response.status_code != 200:
            print(f"❌ Failed to get all collections: {list_response.status_code}")
            print(f"Response: {list_response.text}")
            return False
            
        collections = list_response.json()
        if collections:
            first_collection = collections[0]
            missing_fields = [field for field in required_fields if field not in first_collection]
            
            if missing_fields:
                print(f"❌ List response missing fields: {missing_fields}")
                return False
                
            print("✅ List collections has all required fields")
        
        # Clean up
        client.delete(f"/collections/{collection_id}")
        
        return True
        
    except Exception as e:
        print(f"❌ API consistency test failed: {e}")
        traceback.print_exc()
        return False


def test_uuid_validation_in_api():
    """Test UUID validation in API endpoints."""
    print("\n🔍 Testing UUID validation in API...")
    
    app = create_test_app()
    client = TestClient(app)
    
    try:
        # Test invalid UUID
        response = client.get("/collections/invalid-uuid")
        if response.status_code != 400:
            print(f"❌ Expected 400 for invalid UUID, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
        error_data = response.json()
        if "Invalid UUID format" not in error_data["detail"]:
            print(f"❌ Expected UUID validation error, got: {error_data}")
            return False
            
        print("✅ Invalid UUID properly rejected")
        
        # Test valid UUID that doesn't exist
        response = client.get("/collections/123e4567-e89b-12d3-a456-426614174000")
        if response.status_code != 404:
            print(f"❌ Expected 404 for non-existent collection, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
        print("✅ Non-existent collection returns 404")
        
        return True
        
    except Exception as e:
        print(f"❌ UUID validation test failed: {e}")
        traceback.print_exc()
        return False


async def main():
    """Run all API tests."""
    print("🚀 Starting API fixes verification...\n")
    
    # Initialize database
    await init_test_db()
    
    # Run tests
    tests = [
        test_204_response,
        test_api_response_consistency,
        test_uuid_validation_in_api
    ]
    
    results = []
    for test in tests:
        result = test()
        results.append(result)
    
    await close_db_pool()
    
    passed = sum(results)
    total = len(results)
    
    if passed == total:
        print(f"\n🎉 All {total} API tests passed!")
        return True
    else:
        print(f"\n⚠️  {passed}/{total} tests passed")
        return False


if __name__ == "__main__":
    try:
        result = asyncio.run(main())
        sys.exit(0 if result else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        traceback.print_exc()
        sys.exit(1) 