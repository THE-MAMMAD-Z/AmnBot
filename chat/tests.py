from unittest import mock

from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import ChatSession


class ChatCompletionViewTests(APITestCase):
    def setUp(self):
        patcher = mock.patch("chat.views.requests.post")
        self.addCleanup(patcher.stop)
        self.mock_post = patcher.start()
        mock_response = mock.MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello from OpenRouter"}}]
        }
        self.mock_post.return_value = mock_response

    @override_settings(OPENROUTER_API_KEY="test-key")
    def test_creates_session_and_returns_reply(self):
        url = reverse("chat-completion")
        response = self.client.post(url, {"message": "Hi"}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("session_id", response.data)
        self.assertEqual(response.data["reply"], "Hello from OpenRouter")
        self.assertEqual(len(response.data["messages"]), 2)
        self.assertEqual(ChatSession.objects.count(), 1)

# Create your tests here.
