"""URL configuration for the local catalog harness."""

from django.contrib.auth.views import LoginView, LogoutView
from django.urls import path

from emporio.chat.views import whatsapp_webhook
from emporio.sources.views import (
    source_detail,
    source_edit,
    source_index,
    source_preview,
    source_publish,
    source_rollback,
    source_upload,
)

urlpatterns = [
    path("webhooks/whatsapp", whatsapp_webhook, name="whatsapp-webhook"),
    path("accounts/login/", LoginView.as_view(), name="login"),
    path(
        "accounts/logout/",
        LogoutView.as_view(),
        name="logout",
    ),
    path("equipe/fontes/", source_index, name="staff-source-index"),
    path("equipe/fontes/<str:source>/", source_detail, name="staff-source-detail"),
    path(
        "equipe/fontes/<str:source>/<str:record_id>/editar/", source_edit, name="staff-source-edit"
    ),
    path("equipe/fontes/<str:source>/enviar/", source_upload, name="staff-source-upload"),
    path("equipe/fontes/revisao/<int:draft_id>/", source_preview, name="staff-source-preview"),
    path(
        "equipe/fontes/revisao/<int:draft_id>/publicar/",
        source_publish,
        name="staff-source-publish",
    ),
    path(
        "equipe/fontes/versao/<str:version>/restaurar/",
        source_rollback,
        name="staff-source-rollback",
    ),
]
