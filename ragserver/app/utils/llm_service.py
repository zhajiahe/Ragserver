"""LLM 服务

使用 SiliconFlow 的 OpenAI 兼容 API 进行文本生成
"""

from collections.abc import AsyncIterator
from typing import Any

from loguru import logger
from openai import AsyncOpenAI

from ragserver.config import settings


class LLMService:
    """LLM 文本生成服务"""

    def __init__(
        self,
        model: str = settings.siliconflow_llm_model,
        temperature: float = settings.siliconflow_llm_temperature,
        max_tokens: int = settings.siliconflow_llm_max_tokens,
    ):
        """初始化 SiliconFlow OpenAI 兼容客户端"""
        self.client = AsyncOpenAI(api_key=settings.siliconflow_api_key, base_url=settings.siliconflow_api_base)
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        logger.info(f"LLMService initialized with model: {self.model}")

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float | None = None,
        max_tokens: int | None = None,
        stream: bool = False,
        **kwargs,
    ) -> Any:
        """对话生成

        Args:
            messages: 对话消息列表，格式: [{"role": "user", "content": "..."}]
            temperature: 温度参数，控制随机性（0-2）
            max_tokens: 最大生成 token 数
            stream: 是否使用流式输出
            **kwargs: 其他参数

        Returns:
            生成的回复（非流式）或流式迭代器（流式）
        """
        try:
            if temperature is None:
                temperature = self.temperature
            if max_tokens is None:
                max_tokens = self.max_tokens

            logger.debug(f"开始 LLM 对话，消息数: {len(messages)}, stream: {stream}")

            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=stream,
                **kwargs,
            )

            if stream:
                return response  # 返回流式迭代器
            else:
                content = response.choices[0].message.content
                logger.debug(f"LLM 生成完成，长度: {len(content)}")
                return content

        except Exception as e:
            logger.error(f"LLM 对话失败: {e}")
            raise

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> str:
        """简单文本生成

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            **kwargs: 其他参数

        Returns:
            str: 生成的文本
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        return await self.chat(
            messages=messages, temperature=temperature, max_tokens=max_tokens, stream=False, **kwargs
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        **kwargs,
    ) -> AsyncIterator[str]:
        """流式文本生成

        Args:
            prompt: 用户提示词
            system_prompt: 系统提示词（可选）
            temperature: 温度参数
            max_tokens: 最大生成 token 数
            **kwargs: 其他参数

        Yields:
            str: 生成的文本片段
        """
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        stream = await self.chat(
            messages=messages, temperature=temperature, max_tokens=max_tokens, stream=True, **kwargs
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                yield chunk.choices[0].delta.content

    async def summarize(self, text: str, max_length: int = 200, language: str = "中文") -> str:
        """文本摘要生成

        Args:
            text: 要摘要的文本
            max_length: 摘要最大长度
            language: 输出语言

        Returns:
            str: 摘要文本
        """
        system_prompt = f"你是一个专业的文本摘要助手。请用{language}生成简洁准确的摘要。"
        prompt = f"请为以下文本生成摘要（最多{max_length}字）：\n\n{text}"

        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=0.3,  # 较低的温度以提高一致性
            max_tokens=max_length * 2,  # 预留一些空间
        )

    async def extract_keywords(self, text: str, num_keywords: int = 5, language: str = "中文") -> list[str]:
        """提取关键词

        Args:
            text: 文本内容
            num_keywords: 关键词数量
            language: 语言

        Returns:
            List[str]: 关键词列表
        """
        system_prompt = f"你是一个关键词提取专家。请用{language}提取关键词，每行一个关键词。"
        prompt = f"请从以下文本中提取{num_keywords}个最重要的关键词：\n\n{text}"

        result = await self.generate(prompt=prompt, system_prompt=system_prompt, temperature=0.3, max_tokens=200)

        # 解析关键词（按行分割）
        keywords = [k.strip() for k in result.split("\n") if k.strip()]
        return keywords[:num_keywords]

    async def answer_question(self, question: str, context: str, language: str = "中文") -> str:
        """基于上下文回答问题（用于 RAG）

        Args:
            question: 问题
            context: 上下文信息
            language: 回答语言

        Returns:
            str: 回答
        """
        system_prompt = f"""你是一个专业的问答助手。请根据提供的上下文信息回答问题。
规则：
1. 只基于上下文信息回答，不要编造内容
2. 如果上下文中没有相关信息，请明确说明
3. 使用{language}回答
4. 回答要简洁准确"""

        prompt = f"""上下文信息：
{context}

问题：{question}

请回答："""

        return await self.generate(
            prompt=prompt, system_prompt=system_prompt, temperature=0.7, max_tokens=self.max_tokens
        )


# 创建全局实例
llm_service = LLMService()
