# 文本分块参数配置指南

> 基于 E2E 测试结果和 RAG 系统最佳实践

## 一、参数说明

### 核心参数

| 参数 | 说明 | 默认值 | 建议范围 |
|------|------|--------|----------|
| `max_chunk_size` | 单个块的最大字符数 | 1000 | 500-2000 |
| `min_chunk_size` | 单个块的最小字符数 | 100 | 50-300 |
| `chunk_overlap` | 相邻块之间的重叠字符数 | 200 | 0-500 |

### 策略专用参数

**BM25 语义分块**:
- `similarity_threshold`: 相似度阈值 (默认 0.3，范围 0.0-1.0)

**向量语义分块**:
- `similarity_threshold`: 相似度阈值 (默认 0.7，范围 0.0-1.0)
- `breakpoint_threshold_type`: 边界检测策略
  - `"percentile"`: 百分位数（推荐，自适应）
  - `"fixed"`: 固定阈值
  - `"gradient"`: 梯度变化

---

## 二、推荐配置方案

### 1. 通用文档（推荐）⭐

适用于：技术文档、说明书、新闻文章、博客等

```python
config = {
    "strategy_type": "recursive",
    "config": {
        "max_chunk_size": 800,      # 适中大小，兼顾上下文和精度
        "min_chunk_size": 100,      # 避免过小的无意义块
        "chunk_overlap": 200        # 25% 重叠，保证语义连续性
    }
}
```

**特点**:
- ✅ 速度快（无API调用）
- ✅ 成本低
- ✅ 块大小均匀
- ✅ 适合大多数场景

**测试结果**:
- 块数: 284 个（193K 字符）
- 平均大小: 1090 字符（含重叠）
- 处理速度: < 0.01 秒

---

### 2. 精细检索场景

适用于：法律文档、合同、精确查询场景

```python
config = {
    "strategy_type": "bm25",
    "config": {
        "max_chunk_size": 600,          # 较小块，提高检索精度
        "min_chunk_size": 80,           # 允许较小块保留细节
        "chunk_overlap": 100,           # 17% 重叠
        "similarity_threshold": 0.3     # 低阈值，更多分块点
    }
}
```

**特点**:
- ✅ 块更小更精细（平均 223 字符）
- ✅ 检索召回率高
- ⚠️ 块数多（1476个），检索成本高

**适用场景**:
- 需要精确定位的法律文档
- 多级标题的结构化文档
- FAQ 问答库

---

### 3. 高质量RAG系统（最佳语义理解）

适用于：对答复质量要求高的场景

```python
config = {
    "strategy_type": "semantic",
    "config": {
        "max_chunk_size": 1000,             # 较大块保留更多上下文
        "min_chunk_size": 150,              # 确保语义完整性
        "chunk_overlap": 200,               # 20% 重叠
        "similarity_threshold": 0.7,        # 高阈值识别强语义边界
        "breakpoint_threshold_type": "percentile"  # 自适应
    }
}
```

**特点**:
- ✅ 语义边界最准确
- ✅ 上下文完整性最好
- ✅ 生成答案质量最高
- ⚠️ 需要调用 Embedding API
- ⚠️ 处理时间较长（~20秒/193K字符）

**测试结果**:
- 块数: 458 个
- 平均大小: 573 字符
- 成本: 3016 次 API 调用

---

### 4. 长上下文场景

适用于：需要理解大段落内容的场景（如总结、翻译）

```python
config = {
    "strategy_type": "recursive",
    "config": {
        "max_chunk_size": 1500,     # 大块保留更多上下文
        "min_chunk_size": 200,      # 避免碎片化
        "chunk_overlap": 300        # 20% 重叠
    }
}
```

**特点**:
- ✅ 每个块包含更多上下文
- ✅ 适合长文本理解任务
- ⚠️ 块数少，可能遗漏细节
- ⚠️ Token 消耗大

---

### 5. 快速原型/测试

适用于：开发测试、演示环境

```python
config = {
    "strategy_type": "recursive",
    "config": {
        "max_chunk_size": 500,      # 小块便于观察
        "min_chunk_size": 50,       # 允许小块
        "chunk_overlap": 50         # 10% 重叠
    }
}
```

---

## 三、参数调优指南

### 3.1 `max_chunk_size` (最大块大小)

**影响因素**:

1. **LLM 上下文窗口**
   - GPT-3.5: 推荐 ≤ 1000 字符
   - GPT-4: 可以 1500-2000 字符
   - Claude: 可以更大

2. **文档类型**
   - 技术文档: 800-1200 字符（包含完整段落）
   - 新闻/博客: 600-1000 字符
   - 代码: 400-800 字符（保持函数完整）

3. **检索精度**
   - 精确检索: 500-800 字符（小块）
   - 广泛检索: 1000-1500 字符（大块）

**调优建议**:
```python
# 如果检索结果不准确 → 减小 max_chunk_size
max_chunk_size = 600  # 提高精度

# 如果答案缺少上下文 → 增大 max_chunk_size
max_chunk_size = 1200  # 增加上下文
```

---

### 3.2 `min_chunk_size` (最小块大小)

**作用**: 过滤掉过小的无意义块

**推荐值**:
- 中文: 100-150 字符（约 50-75 个汉字）
- 英文: 80-120 字符（约 15-25 个单词）

**过小的问题**:
```
min_chunk_size = 20  # ❌ 太小
→ 产生 "图 1"、"表 2" 等无意义块
→ 增加存储和检索成本
```

**过大的问题**:
```
min_chunk_size = 500  # ❌ 太大
→ 丢失短段落信息
→ 可能丢失关键细节
```

---

### 3.3 `chunk_overlap` (重叠大小)

**作用**: 避免语义在块边界处断裂

**推荐比例**: 15-25% of `max_chunk_size`

| max_chunk_size | 推荐 chunk_overlap | 比例 |
|----------------|-------------------|------|
| 500 | 100 | 20% |
| 800 | 150-200 | 19-25% |
| 1000 | 200 | 20% |
| 1500 | 250-300 | 17-20% |

**注意事项**:
```python
# ❌ 重叠太小
chunk_overlap = 50  # 对于 max_chunk_size=1000
→ 可能在句子中间切断

# ❌ 重叠太大
chunk_overlap = 800  # 对于 max_chunk_size=1000
→ 大量重复，增加成本

# ✅ 合理重叠
chunk_overlap = 200  # 对于 max_chunk_size=1000
→ 约 1-2 个句子重叠
```

---

## 四、实际场景配置示例

### 场景 1: 客服知识库

```python
{
    "strategy_type": "bm25",
    "config": {
        "max_chunk_size": 600,
        "min_chunk_size": 80,
        "chunk_overlap": 100,
        "similarity_threshold": 0.3
    }
}
```

**理由**: 
- 需要精确匹配用户问题
- 块较小可以定位到具体问答对
- BM25 相似度适合关键词匹配

---

### 场景 2: 技术文档 Q&A

```python
{
    "strategy_type": "semantic",
    "config": {
        "max_chunk_size": 1000,
        "min_chunk_size": 150,
        "chunk_overlap": 200,
        "similarity_threshold": 0.7,
        "breakpoint_threshold_type": "percentile"
    }
}
```

**理由**:
- 技术内容需要理解上下文
- 语义分块保证概念完整性
- 适合复杂技术解释

---

### 场景 3: 企业内部文档搜索

```python
{
    "strategy_type": "recursive",
    "config": {
        "max_chunk_size": 800,
        "min_chunk_size": 100,
        "chunk_overlap": 150
    }
}
```

**理由**:
- 平衡速度和质量
- 无API成本
- 适合大量文档处理

---

### 场景 4: 法律合同分析

```python
{
    "strategy_type": "bm25",
    "config": {
        "max_chunk_size": 500,
        "min_chunk_size": 80,
        "chunk_overlap": 80,
        "similarity_threshold": 0.2  # 低阈值，更多分块点
    }
}
```

**理由**:
- 法律条款需要精确定位
- 小块便于引用具体条款
- 减少重叠以节省成本

---

## 五、性能对比（基于 example.txt - 193K 字符）

| 策略 | 块数 | 平均大小 | 处理时间 | API调用 | 适用场景 |
|------|------|---------|----------|---------|----------|
| Recursive | 284 | 1090字符 | <0.01s | 0 | 通用文档 ⭐ |
| BM25 | 1476 | 223字符 | ~1s | 0 | 精细检索 |
| Semantic | 458 | 573字符 | ~20s | 3016 | 高质量RAG |

---

## 六、调优流程

```
1. 从推荐配置开始
   ↓
2. 运行测试查询
   ↓
3. 评估结果质量
   ↓
4. 调整参数:
   - 检索不准确 → 减小 max_chunk_size
   - 答案缺上下文 → 增大 max_chunk_size
   - 有无意义小块 → 增大 min_chunk_size
   - 语义断裂 → 增大 chunk_overlap
   ↓
5. 重复步骤 2-4
```

---

## 七、常见问题

### Q1: 为什么块大小超过了 max_chunk_size？

A: 由于 `chunk_overlap` 的存在，实际块大小 = 原始大小 + 重叠部分。
测试显示：max_chunk_size=800 时，实际平均 1090 字符。

### Q2: 什么时候使用语义分块？

A: 满足以下条件时推荐：
- 对答复质量要求高
- 有 API 预算
- 文档语义结构复杂
- 不介意处理时间较长

### Q3: min_chunk_size 会丢失信息吗？

A: 不会。min_chunk_size 只是过滤独立的小块，但会合并到相邻块中。
只有最后一个块可以小于 min_chunk_size。

### Q4: 如何选择分块策略？

```
快速决策树:
├─ 需要极高质量？ 
│  └─ Yes → Semantic（向量语义）
├─ 需要精确匹配？
│  └─ Yes → BM25（BM25语义）
└─ 一般场景 → Recursive（递归字符）⭐
```

---

## 八、总结

### 默认推荐配置 ⭐

```python
# 适用于 80% 的场景
config = {
    "strategy_type": "recursive",
    "config": {
        "max_chunk_size": 800,
        "min_chunk_size": 100,
        "chunk_overlap": 200
    }
}
```

**从这里开始，根据实际效果调优！**




