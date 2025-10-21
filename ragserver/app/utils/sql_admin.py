from sqladmin import Admin, ModelView

from ragserver.app.models import (
    User,
    KnowledgeBase,
    Document,
    DocumentChunk,
    ChunkingStrategy,
    APIKey,
    APIUsageLog,
)


class UserAdmin(ModelView):
    model = User


class KnowledgeBaseAdmin(ModelView):
    model = KnowledgeBase


class DocumentAdmin(ModelView):
    model = Document


class DocumentChunkAdmin(ModelView):
    model = DocumentChunk


class ChunkingStrategyAdmin(ModelView):
    model = ChunkingStrategy


class APIKeyAdmin(ModelView):
    model = APIKey


class APIUsageLogAdmin(ModelView):
    model = APIUsageLog


def setup_admin(app, engine) -> Admin:
    admin = Admin(app, engine)
    admin.add_view(UserAdmin)
    admin.add_view(KnowledgeBaseAdmin)
    admin.add_view(DocumentAdmin)
    admin.add_view(DocumentChunkAdmin)
    admin.add_view(ChunkingStrategyAdmin)
    admin.add_view(APIKeyAdmin)
    admin.add_view(APIUsageLogAdmin)
    return admin


