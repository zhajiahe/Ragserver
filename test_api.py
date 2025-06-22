"""
API测试脚本 - 测试RagBackend的所有API接口
"""

import asyncio
import json
import uuid
from typing import Dict, Any

import httpx


class RagBackendAPITester:
    """RagBackend API测试类"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.test_collection_id = None
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    def print_test_result(self, test_name: str, success: bool, details: str = ""):
        """打印测试结果"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"   {details}")
        print()
    
    async def test_health_check(self) -> bool:
        """测试健康检查接口"""
        try:
            response = await self.client.get(f"{self.base_url}/health")
            
            if response.status_code == 200:
                data = response.json()
                expected_fields = ["status", "service", "version"]
                has_all_fields = all(field in data for field in expected_fields)
                
                if has_all_fields and data["status"] == "healthy":
                    self.print_test_result(
                        "健康检查接口", 
                        True, 
                        f"服务状态: {data['status']}, 服务名: {data['service']}, 版本: {data['version']}"
                    )
                    return True
                else:
                    self.print_test_result("健康检查接口", False, f"响应数据格式不正确: {data}")
                    return False
            else:
                self.print_test_result("健康检查接口", False, f"状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test_result("健康检查接口", False, f"请求异常: {e}")
            return False
    
    async def test_create_collection(self) -> bool:
        """测试创建集合接口"""
        try:
            collection_data = {
                "name": f"test_collection_{uuid.uuid4().hex[:8]}",
                "description": "这是一个测试集合",
                "embedding_model": "bge-m3",
                "embedding_provider": "ollama"
            }
            
            response = await self.client.post(
                f"{self.base_url}/collections/",
                json=collection_data
            )
            
            if response.status_code == 201:
                data = response.json()
                expected_fields = ["id", "name", "description", "embedding_model", "embedding_provider", "created_at", "updated_at"]
                has_all_fields = all(field in data for field in expected_fields)
                
                if has_all_fields:
                    self.test_collection_id = data["id"]  # 保存ID用于后续测试
                    self.print_test_result(
                        "创建集合接口", 
                        True, 
                        f"集合ID: {data['id']}, 名称: {data['name']}"
                    )
                    return True
                else:
                    self.print_test_result("创建集合接口", False, f"响应缺少必要字段: {data}")
                    return False
            else:
                error_detail = response.text
                self.print_test_result("创建集合接口", False, f"状态码: {response.status_code}, 错误: {error_detail}")
                return False
                
        except Exception as e:
            self.print_test_result("创建集合接口", False, f"请求异常: {e}")
            return False
    
    async def test_get_collections(self) -> bool:
        """测试获取所有集合接口"""
        try:
            response = await self.client.get(f"{self.base_url}/collections/")
            
            if response.status_code == 200:
                data = response.json()
                
                if isinstance(data, list):
                    self.print_test_result(
                        "获取所有集合接口", 
                        True, 
                        f"返回 {len(data)} 个集合"
                    )
                    return True
                else:
                    self.print_test_result("获取所有集合接口", False, f"响应格式不正确，应为列表: {type(data)}")
                    return False
            else:
                self.print_test_result("获取所有集合接口", False, f"状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test_result("获取所有集合接口", False, f"请求异常: {e}")
            return False
    
    async def test_get_collection_by_id(self) -> bool:
        """测试通过ID获取集合接口"""
        if not self.test_collection_id:
            self.print_test_result("通过ID获取集合接口", False, "没有可用的测试集合ID")
            return False
            
        try:
            response = await self.client.get(f"{self.base_url}/collections/{self.test_collection_id}")
            
            if response.status_code == 200:
                data = response.json()
                expected_fields = ["id", "name", "description", "embedding_model", "embedding_provider", "created_at", "updated_at"]
                has_all_fields = all(field in data for field in expected_fields)
                
                if has_all_fields and data["id"] == self.test_collection_id:
                    self.print_test_result(
                        "通过ID获取集合接口", 
                        True, 
                        f"集合ID: {data['id']}, 名称: {data['name']}"
                    )
                    return True
                else:
                    self.print_test_result("通过ID获取集合接口", False, f"响应数据不正确: {data}")
                    return False
            else:
                self.print_test_result("通过ID获取集合接口", False, f"状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test_result("通过ID获取集合接口", False, f"请求异常: {e}")
            return False
    
    async def test_update_collection(self) -> bool:
        """测试更新集合接口"""
        if not self.test_collection_id:
            self.print_test_result("更新集合接口", False, "没有可用的测试集合ID")
            return False
            
        try:
            update_data = {
                "name": f"updated_test_collection_{uuid.uuid4().hex[:8]}",
                "description": "这是一个更新后的测试集合"
            }
            
            response = await self.client.put(
                f"{self.base_url}/collections/{self.test_collection_id}",
                json=update_data
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data["name"] == update_data["name"] and data["description"] == update_data["description"]:
                    self.print_test_result(
                        "更新集合接口", 
                        True, 
                        f"成功更新集合 {data['id']}, 新名称: {data['name']}"
                    )
                    return True
                else:
                    self.print_test_result("更新集合接口", False, f"更新数据不匹配: {data}")
                    return False
            else:
                self.print_test_result("更新集合接口", False, f"状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test_result("更新集合接口", False, f"请求异常: {e}")
            return False
    
    async def test_delete_collection(self) -> bool:
        """测试删除集合接口"""
        if not self.test_collection_id:
            self.print_test_result("删除集合接口", False, "没有可用的测试集合ID")
            return False
            
        try:
            response = await self.client.delete(f"{self.base_url}/collections/{self.test_collection_id}")
            
            if response.status_code == 204:
                self.print_test_result(
                    "删除集合接口", 
                    True, 
                    f"成功删除集合 {self.test_collection_id}"
                )
                
                # 验证集合确实被删除了
                verify_response = await self.client.get(f"{self.base_url}/collections/{self.test_collection_id}")
                if verify_response.status_code == 404:
                    self.print_test_result("删除验证", True, "集合确实已被删除")
                    return True
                else:
                    self.print_test_result("删除验证", False, "集合可能未被完全删除")
                    return False
            else:
                self.print_test_result("删除集合接口", False, f"状态码: {response.status_code}")
                return False
                
        except Exception as e:
            self.print_test_result("删除集合接口", False, f"请求异常: {e}")
            return False
    
    async def test_get_nonexistent_collection(self) -> bool:
        """测试获取不存在的集合（应返回404）"""
        try:
            fake_id = str(uuid.uuid4())
            response = await self.client.get(f"{self.base_url}/collections/{fake_id}")
            
            if response.status_code == 404:
                self.print_test_result(
                    "获取不存在集合接口", 
                    True, 
                    "正确返回404状态码"
                )
                return True
            else:
                self.print_test_result("获取不存在集合接口", False, f"状态码: {response.status_code}，应为404")
                return False
                
        except Exception as e:
            self.print_test_result("获取不存在集合接口", False, f"请求异常: {e}")
            return False
    
    async def run_all_tests(self):
        """运行所有测试"""
        print("🚀 开始API接口测试\n")
        print("=" * 50)
        
        tests = [
            ("健康检查", self.test_health_check),
            ("创建集合", self.test_create_collection),
            ("获取所有集合", self.test_get_collections),
            ("通过ID获取集合", self.test_get_collection_by_id),
            ("更新集合", self.test_update_collection),
            ("获取不存在的集合", self.test_get_nonexistent_collection),
            ("删除集合", self.test_delete_collection),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                result = await test_func()
                if result:
                    passed += 1
            except Exception as e:
                print(f"❌ FAIL {test_name} - 测试执行异常: {e}\n")
        
        print("=" * 50)
        print(f"📊 测试结果统计:")
        print(f"   总测试数: {total}")
        print(f"   通过: {passed}")
        print(f"   失败: {total - passed}")
        print(f"   成功率: {passed/total*100:.1f}%")
        
        if passed == total:
            print("🎉 所有测试通过！")
        else:
            print("⚠️  部分测试失败，请检查服务状态")


async def main():
    """主函数"""
    import sys
    
    # 可以通过命令行参数指定服务器地址
    base_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080"
    
    print(f"目标服务器: {base_url}")
    print("请确保RagBackend服务正在运行...\n")
    
    async with RagBackendAPITester(base_url) as tester:
        await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
