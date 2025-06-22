"""Embedding service implementations."""

import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import asyncio
import aiohttp
import httpx
from openai import AsyncOpenAI

from ragbackend.config import (
    OLLAMA_BASE_URL, OLLAMA_EMBED_MODEL,
    SILICONFLOW_API_KEY, SILICONFLOW_BASE_URL, SILICONFLOW_MODEL,
    OPENAI_API_KEY,
    DEFAULT_EMBEDDING_MODEL
)

logger = logging.getLogger(__name__)


class EmbeddingService(ABC):
    """抽象嵌入服务基类"""
    
    @abstractmethod
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化"""
        pass
    
    @abstractmethod
    async def embed_query(self, text: str) -> List[float]:
        """单个查询文本向量化"""
        pass
    
    @property
    @abstractmethod
    def dimension(self) -> int:
        """向量维度"""
        pass


class OllamaEmbeddingService(EmbeddingService):
    """Ollama嵌入服务"""
    
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_EMBED_MODEL):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self._dimension = 1024  # bge-m3默认维度
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化"""
        embeddings = []
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            for text in texts:
                try:
                    response = await client.post(
                        f"{self.base_url}/api/embeddings",
                        json={
                            "model": self.model,
                            "prompt": text
                        }
                    )
                    response.raise_for_status()
                    result = response.json()
                    embeddings.append(result["embedding"])
                except Exception as e:
                    logger.error(f"Ollama嵌入失败: {e}")
                    raise
        
        return embeddings
    
    async def embed_query(self, text: str) -> List[float]:
        """单个查询文本向量化"""
        embeddings = await self.embed_texts([text])
        return embeddings[0]
    
    @property
    def dimension(self) -> int:
        return self._dimension


class OpenAIEmbeddingService(EmbeddingService):
    """OpenAI嵌入服务"""
    
    def __init__(self, api_key: str = OPENAI_API_KEY, model: str = "text-embedding-ada-002"):
        if not api_key:
            raise ValueError("OpenAI API key is required")
        
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self._dimension = 1536 if model == "text-embedding-ada-002" else 1024
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化"""
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts
            )
            return [data.embedding for data in response.data]
        except Exception as e:
            logger.error(f"OpenAI嵌入失败: {e}")
            raise
    
    async def embed_query(self, text: str) -> List[float]:
        """单个查询文本向量化"""
        embeddings = await self.embed_texts([text])
        return embeddings[0]
    
    @property
    def dimension(self) -> int:
        return self._dimension


class SiliconFlowEmbeddingService(EmbeddingService):
    """硅基流动嵌入服务"""
    
    def __init__(self, api_key: str = SILICONFLOW_API_KEY, base_url: str = SILICONFLOW_BASE_URL, model: str = SILICONFLOW_MODEL):
        if not api_key:
            raise ValueError("SiliconFlow API key is required")
        
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self._dimension = 1024  # BAAI/bge-m3默认维度
    
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """批量文本向量化"""
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model,
                        "input": texts
                    }
                )
                response.raise_for_status()
                result = response.json()
                return [data["embedding"] for data in result["data"]]
        except Exception as e:
            logger.error(f"SiliconFlow嵌入失败: {e}")
            raise
    
    async def embed_query(self, text: str) -> List[float]:
        """单个查询文本向量化"""
        embeddings = await self.embed_texts([text])
        return embeddings[0]
    
    @property
    def dimension(self) -> int:
        return self._dimension


class EmbeddingServiceFactory:
    """嵌入服务工厂"""
    
    @staticmethod
    def create_service(provider: str, **kwargs) -> EmbeddingService:
        """
        创建嵌入服务实例
        
        Args:
            provider: 服务提供商 (ollama, openai, siliconflow)
            **kwargs: 额外参数
        
        Returns:
            EmbeddingService: 嵌入服务实例
        """
        provider = provider.lower()
        
        if provider == "ollama":
            return OllamaEmbeddingService(**kwargs)
        elif provider == "openai":
            return OpenAIEmbeddingService(**kwargs)
        elif provider == "siliconflow":
            return SiliconFlowEmbeddingService(**kwargs)
        else:
            raise ValueError(f"不支持的嵌入服务提供商: {provider}")


# 全局嵌入服务实例缓存
_embedding_services: Dict[str, EmbeddingService] = {}


async def get_embedding_service(provider: str = DEFAULT_EMBEDDING_MODEL) -> EmbeddingService:
    """
    获取嵌入服务实例（单例模式）
    
    Args:
        provider: 服务提供商
    
    Returns:
        EmbeddingService: 嵌入服务实例
    """
    if provider not in _embedding_services:
        _embedding_services[provider] = EmbeddingServiceFactory.create_service(provider)
    
    return _embedding_services[provider]


async def get_collection_embedding_service(collection: Dict[str, Any]) -> EmbeddingService:
    """
    根据集合配置获取嵌入服务
    
    Args:
        collection: 集合信息
    
    Returns:
        EmbeddingService: 嵌入服务实例
    """
    provider = collection.get('embedding_provider', DEFAULT_EMBEDDING_MODEL)
    return await get_embedding_service(provider) 