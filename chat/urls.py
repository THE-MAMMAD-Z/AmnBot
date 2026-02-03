from django.urls import path

from .views import ChatCompletionView, ChatSessionDetailView

urlpatterns = [
    path("chat/", ChatCompletionView.as_view(), name="chat-completion"),
    path("chat/<uuid:session_id>/", ChatSessionDetailView.as_view(), name="chat-session-detail"),
]

