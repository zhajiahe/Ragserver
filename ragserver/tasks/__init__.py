"""
Taskiq 任务队列配置

定义全局 broker 和任务注册
"""
from taskiq import TaskiqScheduler
from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from ragserver.config import settings

# 创建 Redis broker
redis_broker = ListQueueBroker(
    url=settings.get_taskiq_broker_url,
)

# 创建 Result Backend（用于存储任务结果）
result_backend = RedisAsyncResultBackend(
    redis_url=settings.get_taskiq_result_backend_url,
)

# 将 result backend 绑定到 broker
redis_broker = redis_broker.with_result_backend(result_backend)

# 导出 broker
broker = redis_broker

# 导入所有任务模块以注册任务
from ragserver.tasks import document_processing  # noqa: F401, E402

__all__ = ["broker"]

