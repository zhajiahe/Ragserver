#!/usr/bin/env python3
"""Test script to verify the fixes."""

import asyncio
import sys
import traceback
from ragbackend.database.connection import init_db_pool, init_database_tables, close_db_pool
from ragbackend.database.collections import create_collection, get_collection_by_id, get_all_collections
from ragbackend.utils.validators import validate_uuid, validate_and_sanitize_table_name


async def test_database_schema():
    """Test if database schema is correctly created."""
    print("🔍 Testing database schema...")
    
    try:
        await init_db_pool()
        await init_database_tables()
        print("✅ Database initialized successfully")
        
        # Test creating a collection with embedding_provider field
        collection = await create_collection(
            name="测试集合",
            description="这是一个测试集合",
            embedding_model="bge-m3",
            embedding_provider="ollama"
        )
        
        print(f"✅ Collection created: {collection['id']}")
        print(f"   - Name: {collection['name']}")
        print(f"   - Embedding Model: {collection['embedding_model']}")
        print(f"   - Embedding Provider: {collection['embedding_provider']}")
        
        return collection['id']
        
    except Exception as e:
        print(f"❌ Database schema test failed: {e}")
        traceback.print_exc()
        return None


async def test_uuid_validation():
    """Test UUID validation functionality."""
    print("\n🔍 Testing UUID validation...")
    
    try:
        # Test valid UUID
        valid_uuid = "123e4567-e89b-12d3-a456-426614174000"
        result = validate_uuid(valid_uuid)
        print(f"✅ Valid UUID accepted: {result}")
        
        # Test table name generation
        table_name = validate_and_sanitize_table_name(valid_uuid)
        print(f"✅ Safe table name generated: {table_name}")
        
        # Test invalid UUID
        try:
            validate_uuid("invalid-uuid")
            print("❌ Invalid UUID should have been rejected")
        except Exception:
            print("✅ Invalid UUID correctly rejected")
            
        return True
        
    except Exception as e:
        print(f"❌ UUID validation test failed: {e}")
        return False


async def test_api_response_consistency(collection_id: str):
    """Test API response consistency."""
    print("\n🔍 Testing API response consistency...")
    
    try:
        # Test get_collection_by_id
        collection = await get_collection_by_id(collection_id)
        if collection:
            required_fields = ['id', 'name', 'description', 'embedding_model', 'embedding_provider', 'created_at', 'updated_at']
            missing_fields = [field for field in required_fields if field not in collection]
            
            if missing_fields:
                print(f"❌ Missing fields in get_collection_by_id: {missing_fields}")
                return False
            else:
                print("✅ get_collection_by_id returns all required fields")
        
        # Test get_all_collections
        collections = await get_all_collections()
        if collections:
            collection = collections[0]
            missing_fields = [field for field in required_fields if field not in collection]
            
            if missing_fields:
                print(f"❌ Missing fields in get_all_collections: {missing_fields}")
                return False
            else:
                print("✅ get_all_collections returns all required fields")
        
        return True
        
    except Exception as e:
        print(f"❌ API response consistency test failed: {e}")
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("🚀 Starting fixes verification...\n")
    
    # Test 1: Database schema
    collection_id = await test_database_schema()
    if not collection_id:
        print("\n❌ Database schema test failed, stopping tests")
        return False
    
    # Test 2: UUID validation
    uuid_test_passed = await test_uuid_validation()
    if not uuid_test_passed:
        print("\n❌ UUID validation test failed")
    
    # Test 3: API response consistency
    api_test_passed = await test_api_response_consistency(collection_id)
    if not api_test_passed:
        print("\n❌ API response consistency test failed")
    
    await close_db_pool()
    
    if uuid_test_passed and api_test_passed:
        print("\n🎉 All tests passed! Fixes are working correctly.")
        return True
    else:
        print("\n⚠️  Some tests failed. Please check the issues above.")
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