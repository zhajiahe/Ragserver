from sqladmin import Admin, ModelView

from ragserver.app.models import (
    APIKey,
    APIUsageLog,
    Collection,
    Document,
    DocumentChunk,
    User,
)


class UserAdmin(ModelView):
    model = User


class CollectionAdmin(ModelView):
    model = Collection


class DocumentAdmin(ModelView):
    model = Document


class DocumentChunkAdmin(ModelView):
    model = DocumentChunk


class APIKeyAdmin(ModelView):
    model = APIKey


class APIUsageLogAdmin(ModelView):
    model = APIUsageLog


def setup_admin(app, engine) -> Admin:
    admin = Admin(app, engine)
    admin.add_view(UserAdmin)
    admin.add_view(CollectionAdmin)
    admin.add_view(DocumentAdmin)
    admin.add_view(DocumentChunkAdmin)
    admin.add_view(APIKeyAdmin)
    admin.add_view(APIUsageLogAdmin)
    return admin
