"""Embedding 向量生成服务

使用 SiliconFlow 的 OpenAI 兼容 API 生成文本向量
"""

from loguru import logger
from openai import AsyncOpenAI

from ragserver.config import settings


class EmbeddingService:
    """Embedding 向量生成服务"""

    def __init__(self):
        """初始化 SiliconFlow OpenAI 兼容客户端"""
        self.client = AsyncOpenAI(
            api_key=settings.siliconflow_api_key,
            base_url=settings.siliconflow_api_base,
        )
        self.model = settings.default_embedding_model
        logger.info(f"EmbeddingService initialized with model: {self.model}")

    async def encode(self, texts: list[str]) -> list[list[float]]:
        """生成文本向量

        Args:
            texts: 文本列表

        Returns:
            List[List[float]]: 向量列表

        Raises:
            Exception: 向量生成失败时抛出异常
        """
        try:
            logger.debug(f"开始生成 {len(texts)} 个文本的向量")

            # SiliconFlow 支持批量请求
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
                encoding_format="float",
            )

            # 提取向量
            embeddings = [item.embedding for item in response.data]

            logger.debug(f"向量生成成功，维度: {len(embeddings[0])}")
            return embeddings

        except Exception as e:
            logger.error(f"生成向量失败: {e}")
            raise

    async def encode_single(self, text: str) -> list[float]:
        """生成单个文本的向量

        Args:
            text: 文本内容

        Returns:
            List[float]: 向量
        """
        embeddings = await self.encode([text])
        return embeddings[0]

    async def encode_batch(self, texts: list[str], batch_size: int = None) -> list[list[float]]:
        """批量生成向量（自动分批处理）

        Args:
            texts: 文本列表
            batch_size: 批处理大小，默认使用配置中的值

        Returns:
            List[List[float]]: 向量列表
        """
        if batch_size is None:
            batch_size = settings.embedding_batch_size

        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i : i + batch_size]
            batch_embeddings = await self.encode(batch_texts)
            all_embeddings.extend(batch_embeddings)

            logger.info(f"向量生成进度: {min(i + batch_size, len(texts))}/{len(texts)}")

        return all_embeddings


# 创建全局实例
embedding_service = EmbeddingService()
