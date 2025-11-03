import re
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from abc import ABC, abstractmethod
from ragserver.app.utils.embedding_service import embedding_service
import numpy as np
from typing import List, Dict, Any
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class BaseChunker(ABC):
    """文本分割器基类，提供公共的工具方法"""

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @abstractmethod
    async def split_text(self, text: str) -> List[Dict[str, Any]]:
        """分割文本的抽象方法"""
        pass

    @staticmethod
    def _split_into_segments(text: str) -> List[str]:
        """将文本分割成段落或句子（公共方法）"""
        # 优先按段落分割
        paragraphs = re.split(r'\n\s*\n', text)
        paragraphs = [p.strip() for p in paragraphs if p.strip()]

        # 如果段落太少，按句子分割
        if len(paragraphs) < 3:
            sentences = re.split(r'(?<=[.!?。!?])\s+', text)
            return [s.strip() for s in sentences if s.strip()]

        return paragraphs

    @staticmethod
    def _extract_overlap_text(text: str, target_size: int) -> str:
        """从文本末尾提取指定大小的重叠部分（保持句子完整）"""
        # 按句子分割
        sentences = re.split(r'(?<=[.!?。!?])\s+', text)

        if not sentences:
            return ""

        # 从后向前收集句子，直到达到目标大小
        overlap_sentences = []
        current_size = 0

        for sentence in reversed(sentences):
            sentence_size = len(sentence)

            # 如果加上这个句子不超过目标大小，就添加
            if current_size + sentence_size <= target_size:
                overlap_sentences.insert(0, sentence)
                current_size += sentence_size
            else:
                # 已经达到目标大小，停止
                break

        return " ".join(overlap_sentences)

    @staticmethod
    def _format_chunks(chunks: List[str]) -> List[Dict[str, Any]]:
        """格式化块结果为统一格式"""
        return [
            {
                "content": chunk,
                "metadata": {
                    "chunk_index": i,
                    "chunk_size": len(chunk),
                    "char_count": len(chunk)
                }
            }
            for i, chunk in enumerate(chunks)
        ]

    def _add_overlap(self, chunks: List[str]) -> List[str]:
        """添加块之间的重叠"""
        if len(chunks) <= 1:
            return chunks

        overlapped_chunks = [chunks[0]]

        for i in range(1, len(chunks)):
            # 从前一个块的末尾提取重叠部分
            overlap_text = self._extract_overlap_text(
                chunks[i-1],
                self.chunk_overlap
            )

            if overlap_text:
                # 将重叠部分添加到当前块的开头
                overlapped_chunks.append(overlap_text + "\n\n" + chunks[i])
            else:
                overlapped_chunks.append(chunks[i])

        return overlapped_chunks


class RecursiveCharacterChunker(BaseChunker):
    """递归字符文本分割器"""

    def __init__(self, chunk_size=1000, chunk_overlap=200, separators=None):
        """
        初始化递归字符文本分割器

        参数:
            chunk_size: 块大小（字符数）
            chunk_overlap: 块重叠大小（字符数）
            separators: 分隔符列表，按优先级排序，如果为None则使用默认设置
        """
        super().__init__(chunk_size, chunk_overlap)

        # 默认分隔符，按优先级排序
        self.separators = separators or [
            "\n\n",  # 段落
            "\n",    # 换行
            ". ",    # 句子
            "! ",    # 感叹句
            "? ",    # 问句
            ";",     # 分号
            ",",     # 逗号
            " ",     # 空格（单词）
            ""       # 字符
        ]

    async def split_text(self, text: str) -> List[Dict[str, Any]]:
        """
        递归地将文本分割成块

        参数:
            text: 要分割的文本

        返回:
            包含分割后文本块的列表，每个块包含内容和元数据
        """
        chunks = self._split_text_recursive(text, self.separators)

        # 处理块重叠
        if self.chunk_overlap > 0:
            chunks = self._merge_chunks_with_overlap(chunks)

        return self._format_chunks(chunks)
    
    def _split_text_recursive(self, text: str, separators: List[str]) -> List[str]:
        """
        递归分割文本
        
        参数:
            text: 要分割的文本
            separators: 当前可用的分隔符列表
            
        返回:
            分割后的文本块列表
        """
        # 如果文本长度小于块大小，直接返回
        if len(text) <= self.chunk_size:
            return [text]
        
        # 如果没有更多分隔符，则按块大小强制分割
        if not separators:
            return self._split_by_character(text)
        
        # 获取当前分隔符和剩余分隔符
        separator = separators[0]
        next_separators = separators[1:]
        
        # 使用当前分隔符分割文本
        splits = text.split(separator)
        
        # 如果分割后只有一个元素，使用下一个分隔符
        if len(splits) == 1:
            return self._split_text_recursive(text, next_separators)
        
        # 处理分割后的文本
        chunks = []
        current_chunk = []
        current_length = 0
        
        for split in splits:
            # 如果不是第一个分割，添加分隔符
            if current_chunk:
                split_with_separator = separator + split
            else:
                split_with_separator = split
            
            split_length = len(split_with_separator)
            
            # 如果添加当前分割会超过块大小
            if current_length + split_length > self.chunk_size:
                # 如果当前块不为空，添加到结果
                if current_chunk:
                    chunk_text = "".join(current_chunk)
                    chunks.append(chunk_text)
                
                # 如果当前分割本身超过块大小，递归处理
                if split_length > self.chunk_size:
                    sub_chunks = self._split_text_recursive(split_with_separator, next_separators)
                    chunks.extend(sub_chunks)
                    current_chunk = []
                    current_length = 0
                else:
                    # 开始新的块
                    current_chunk = [split_with_separator]
                    current_length = split_length
            else:
                # 添加到当前块
                current_chunk.append(split_with_separator)
                current_length += split_length
        
        # 添加最后一个块
        if current_chunk:
            chunk_text = "".join(current_chunk)
            chunks.append(chunk_text)
        
        # 处理块重叠
        if self.chunk_overlap > 0:
            return self._merge_chunks_with_overlap(chunks)
        
        return chunks
    
    def _split_by_character(self, text: str) -> List[str]:
        """
        按字符强制分割文本
        
        参数:
            text: 要分割的文本
            
        返回:
            分割后的文本块列表
        """
        chunks = []
        for i in range(0, len(text), self.chunk_size):
            chunks.append(text[i:i + self.chunk_size])
        return chunks
    
    def _merge_chunks_with_overlap(self, chunks: List[str]) -> List[str]:
        """
        处理块之间的重叠
        
        参数:
            chunks: 原始文本块列表
            
        返回:
            处理重叠后的文本块列表
        """
        if not chunks or len(chunks) == 1:
            return chunks
        
        result = []
        for i in range(len(chunks)):
            if i == 0:
                # 第一个块不需要前向重叠
                result.append(chunks[i])
            else:
                # 获取前一个块的末尾部分作为重叠
                prev_chunk = chunks[i-1]
                overlap_size = min(self.chunk_overlap, len(prev_chunk))
                overlap_text = prev_chunk[-overlap_size:]
                
                # 将重叠部分添加到当前块的开头
                result.append(overlap_text + chunks[i])
        
        return result





class Bm25TextChunker(BaseChunker):
    """基于BM25的语义文本分割器"""
    
    def __init__(self, chunk_size=1000, chunk_overlap=200, similarity_threshold=0.3):
        """
        初始化BM25文本分割器

        参数:
            chunk_size: 块大小（字符数）
            chunk_overlap: 块重叠大小（字符数）
            similarity_threshold: 相似度阈值，用于判断是否合并段落
        """
        super().__init__(chunk_size, chunk_overlap)
        self.similarity_threshold = similarity_threshold

    async def split_text(self, text: str) -> List[Dict[str, Any]]:
        """分割文本为语义相关的块"""
        # 分割成句子/段落
        segments = self._split_into_segments(text)

        if len(segments) <= 1:
            return self._format_chunks([text])

        # 使用滑动窗口 + 相似度合并
        chunks = self._create_chunks_with_similarity(segments)

        # 添加重叠
        if self.chunk_overlap > 0:
            chunks = self._add_overlap(chunks)

        return self._format_chunks(chunks)

    def _create_chunks_with_similarity(self, segments: List[str]) -> List[str]:
        """使用相似度创建文本块"""
        if not segments:
            return []
        
        chunks = []
        current_chunk = [segments[0]]
        current_length = len(segments[0])
        
        for i in range(1, len(segments)):
            segment = segments[i]
            segment_length = len(segment)
            
            # 检查是否超过大小限制
            if current_length + segment_length + 2 > self.chunk_size:  # +2 for "\n\n"
                # 检查相似度决定是否强制合并
                similarity = self._calculate_similarity(
                    "\n\n".join(current_chunk), 
                    segment
                )
                
                if similarity < self.similarity_threshold:
                    # 相似度低，开始新块
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = [segment]
                    current_length = segment_length
                else:
                    # 相似度高但超过大小，先保存当前块再开始新块
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = [segment]
                    current_length = segment_length
            else:
                # 未超过大小，检查相似度
                similarity = self._calculate_similarity(
                    "\n\n".join(current_chunk), 
                    segment
                )
                
                if similarity >= self.similarity_threshold or len(current_chunk) < 2:
                    # 相似度足够或块太小，添加到当前块
                    current_chunk.append(segment)
                    current_length += segment_length + 2
                else:
                    # 相似度不够，开始新块
                    chunks.append("\n\n".join(current_chunk))
                    current_chunk = [segment]
                    current_length = segment_length
        
        # 添加最后一个块
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
        
        return chunks
    
    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的余弦相似度"""
        try:
            # 使用 TF-IDF + 余弦相似度（比 BM25 更适合文档相似度）
            vectorizer = TfidfVectorizer(
                token_pattern=r"(?u)\b\w+\b",
                min_df=1,
                max_df=1.0
            )
            
            tfidf_matrix = vectorizer.fit_transform([text1, text2])
            similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
            
            return similarity
        except:
            # 如果计算失败（如文本太短），返回默认值
            return 0.5
    


class SemanticChunker(BaseChunker):
    """基于向量语义边界的智能分块工具"""

    def __init__(
        self,
        similarity_threshold: float = 0.7,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1000,
        chunk_overlap: int = 50,
        breakpoint_threshold_type: str = "percentile"
    ):
        """
        初始化语义分块器

        参数:
            similarity_threshold: 相似度阈值（用于 fixed 模式）
            min_chunk_size: 最小块大小（字符数）
            max_chunk_size: 最大块大小（字符数）
            chunk_overlap: 块重叠大小（字符数）
            breakpoint_threshold_type: 边界检测策略
                - "fixed": 固定阈值
                - "percentile": 百分位数（更自适应）
                - "gradient": 梯度变化（检测相似度骤降）
        """
        super().__init__(max_chunk_size, chunk_overlap)
        self.similarity_threshold = similarity_threshold
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.breakpoint_threshold_type = breakpoint_threshold_type

    async def split_text(self, text: str) -> List[Dict[str, Any]]:
        """基于语义边界对文本进行分块"""
        # 分割成段落
        paragraphs = self._split_into_segments(text)

        if len(paragraphs) <= 1:
            return self._format_chunks([text])

        # 计算嵌入向量（异步批量处理）
        embeddings = await embedding_service.encode_batch(paragraphs)

        # 计算相邻段落之间的相似度
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = self._compute_similarity(embeddings[i], embeddings[i+1])
            similarities.append(sim)

        # 识别语义边界
        breakpoints = self._identify_breakpoints(similarities, paragraphs)

        # 根据边界点创建文本块
        chunks = self._create_chunks(paragraphs, breakpoints)

        # 添加重叠
        if self.chunk_overlap > 0:
            chunks = self._add_overlap(chunks)

        return self._format_chunks(chunks)
    
    # ==========================================
    # 功能2: 三种边界检测策略
    # ==========================================
    
    def _identify_breakpoints(
        self, 
        similarities: List[float], 
        paragraphs: List[str]
    ) -> List[int]:
        """
        识别语义边界点
        
        返回: 边界点的索引列表（表示在哪些位置切分）
        """
        if not similarities:
            return []
        
        breakpoints = []
        
        if self.breakpoint_threshold_type == "fixed":
            # 策略1: 固定阈值
            # 当相似度低于阈值时，认为是语义边界
            for i, sim in enumerate(similarities):
                if sim < self.similarity_threshold:
                    breakpoints.append(i + 1)
        
        elif self.breakpoint_threshold_type == "percentile":
            # 策略2: 百分位数（自适应）
            # 找出相似度最低的25%作为边界
            threshold = np.percentile(similarities, 25)
            for i, sim in enumerate(similarities):
                if sim < threshold:
                    breakpoints.append(i + 1)
        
        elif self.breakpoint_threshold_type == "gradient":
            # 策略3: 梯度变化（最智能）
            # 检测相似度骤降的位置
            if len(similarities) < 2:
                return []
            
            # 计算相似度的变化率（梯度）
            gradients = np.diff(similarities)
            
            # 找到负梯度最大的点（相似度下降最快的地方）
            threshold = np.percentile(gradients, 25)
            for i, grad in enumerate(gradients):
                if grad < threshold:
                    breakpoints.append(i + 1)
        
        return sorted(set(breakpoints))
    
    def _create_chunks(
        self, 
        paragraphs: List[str], 
        breakpoints: List[int]
    ) -> List[str]:
        """根据边界点创建文本块"""
        chunks = []
        start_idx = 0
        
        # 添加最后一个边界点
        breakpoints = breakpoints + [len(paragraphs)]
        
        for breakpoint in breakpoints:
            # 收集段落
            chunk_paragraphs = paragraphs[start_idx:breakpoint]
            chunk_text = "\n\n".join(chunk_paragraphs)
            
            # 检查大小限制
            if len(chunk_text) > self.max_chunk_size:
                # 块太大，需要进一步分割
                sub_chunks = self._split_large_chunk(chunk_paragraphs)
                chunks.extend(sub_chunks)
            elif len(chunk_text) < self.min_chunk_size and chunks:
                # 块太小，合并到前一个块
                chunks[-1] = chunks[-1] + "\n\n" + chunk_text
            else:
                chunks.append(chunk_text)
            
            start_idx = breakpoint
        
        return chunks
    
    def _split_large_chunk(self, paragraphs: List[str]) -> List[str]:
        """分割过大的块"""
        chunks = []
        current_chunk = []
        current_size = 0
        
        for para in paragraphs:
            para_size = len(para)
            
            if current_size + para_size > self.max_chunk_size and current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = [para]
                current_size = para_size
            else:
                current_chunk.append(para)
                current_size += para_size + 2  # +2 for "\n\n"
        
        if current_chunk:
            chunks.append("\n\n".join(current_chunk))
        
        return chunks

    def _compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        import numpy as np
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)

        # 计算余弦相似度
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))


# ==================== 工厂模式 ====================

class ChunkerFactory:
    """分块器工厂类"""

    @staticmethod
    def create_chunker(strategy_type: str, config: Dict[str, Any]) -> BaseChunker:
        """
        根据策略类型创建对应的分块器

        Args:
            strategy_type: 分块策略类型
                - "recursive": 递归字符分块
                - "bm25": BM25语义分块
                - "semantic": 向量语义分块
            config: 分块配置

        Returns:
            BaseChunker: 分块器实例

        Raises:
            ValueError: 未知的分块策略
        """
        chunk_size = config.get("max_chunk_size", 1000)
        chunk_overlap = config.get("chunk_overlap", 200)

        if strategy_type == "recursive":
            separators = config.get("separators", None)
            return RecursiveCharacterChunker(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=separators
            )

        elif strategy_type == "bm25":
            similarity_threshold = config.get("similarity_threshold", 0.3)
            return Bm25TextChunker(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                similarity_threshold=similarity_threshold
            )

        elif strategy_type == "semantic":
            similarity_threshold = config.get("similarity_threshold", 0.7)
            min_chunk_size = config.get("min_chunk_size", 100)
            breakpoint_threshold_type = config.get("breakpoint_threshold_type", "percentile")

            return SemanticChunker(
                similarity_threshold=similarity_threshold,
                min_chunk_size=min_chunk_size,
                max_chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                breakpoint_threshold_type=breakpoint_threshold_type
            )

        else:
            raise ValueError(f"Unknown chunking strategy: {strategy_type}")


async def chunk_text(text: str, chunking_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    对文本进行分块（统一入口函数）

    Args:
        text: 要分块的文本
        chunking_config: 分块配置字典
            - strategy_type: 分块策略类型
            - config: 策略具体配置

    Returns:
        List[Dict[str, Any]]: 分块结果列表，每个元素包含 content 和 metadata

    Example:
        ```python
        config = {
            "strategy_type": "semantic",
            "config": {
                "max_chunk_size": 1000,
                "chunk_overlap": 200,
                "similarity_threshold": 0.7
            }
        }
        chunks = await chunk_text("长文本...", config)
        ```
    """
    strategy_type = chunking_config.get("strategy_type", "recursive")
    config = chunking_config.get("config", {})

    chunker = ChunkerFactory.create_chunker(strategy_type, config)
    return await chunker.split_text(text)
