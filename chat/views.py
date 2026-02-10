import logging
import json
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.conf import settings

from .models import ChatMessage, ChatSession
from .serializers import (
    ChatMessageSerializer,
    ChatRequestSerializer,
    ChatSessionSerializer,
)
from .url_scripts import AVAILABLE_SCRIPTS

logger = logging.getLogger(__name__)
api_key = settings.API_KEY
model_name = settings.MODEL_NAME
base_url = settings.BASE_URL
temperature = settings.TEMPERATURE

class ChatCompletionView(APIView):
    """Process a URL with parallel scripts and get AI analysis."""

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        url = serializer.validated_data["url"].strip()
        if not url:
            return Response(
                {"detail": "URL cannot be empty."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = self._get_or_create_session(serializer.validated_data.get("session_id"))

        try:
            # Process URL with scripts in parallel using multithreading
            logger.info(f"Starting parallel processing of URL: {url}")
            script_results = self._process_url_with_scripts(url)
            logger.info(f"Script processing completed for {url}, passing to AI model")
            
            # Format script results for display
            script_results_text = json.dumps(script_results, indent=2)
            user_message_content = f"Analyze URL and find vulrnability: {url}\n\nScript Results:\n{script_results_text}"
            
            # Create user message with the full context (URL + script results)
            user_message = ChatMessage.objects.create(
                session=session,
                role=ChatMessage.Role.USER,
                content=user_message_content,
            )
            print("before llm sending requets ++++ ")
            # Pass the script results to the AI model
            assistant_reply = self._call_groq_with_script_results(session, url, script_results)
            
        except Exception as exc:
            logger.exception(f"Error processing URL {url}")
            return Response(
                {"detail": f"Error processing URL: {str(exc)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        assistant_message = ChatMessage.objects.create(
            session=session,
            role=ChatMessage.Role.ASSISTANT,
            content=assistant_reply,
        )

        messages_payload = ChatMessageSerializer(session.messages.all(), many=True).data

        return Response(
            {
                "session_id": str(session.id),
                "reply": assistant_message.content,
                "script_results": script_results,
                "messages": messages_payload,
            }
        )

    def _get_or_create_session(self, session_id):
        if session_id:
            return get_object_or_404(ChatSession, id=session_id)
        return ChatSession.objects.create()

    def _run_script(self, script_func, url: str) -> Dict[str, Any]:
        """Run a single script function on a URL."""
        try:
            return script_func(url)
        except Exception as e:
            logger.error(f"Error running script {script_func.__name__} on {url}: {str(e)}")
            return {
                'script_name': script_func.__name__,
                'status': 'error',
                'error': str(e),
            }

    def _process_url_with_scripts(self, url: str) -> Dict[str, Any]:
        """
        Process a URL by running all available scripts in parallel using multithreading.
        
        Args:
            url: The URL to process
            
        Returns:
            Dictionary containing results from all scripts
        """
        results = {
            'url': url,
            'scripts_executed': len(AVAILABLE_SCRIPTS),
            'results': [],
        }
        
        # Use ThreadPoolExecutor to run scripts in parallel
        with ThreadPoolExecutor(max_workers=len(AVAILABLE_SCRIPTS)) as executor:
            # Submit all tasks
            future_to_script = {
                executor.submit(self._run_script, script, url): script
                for script in AVAILABLE_SCRIPTS
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_script):
                script = future_to_script[future]
                try:
                    result = future.result()
                    results['results'].append(result)
                    logger.info(f"Script {script.__name__} completed for {url}")
                except Exception as e:
                    logger.error(f"Script {script.__name__} failed for {url}: {str(e)}")
                    results['results'].append({
                        'script_name': script.__name__,
                        'status': 'error',
                        'error': str(e),
                    })
        
        return results

    def _call_groq_with_script_results(self, session: ChatSession, url: str, script_results: dict) -> str:
        """Call Groq API with script results to get AI analysis."""
        if not api_key:
            raise ValueError("Set the API_KEY environment variable to continue.")

        # Build message history (includes the user message we just created with script results)
        history = self._build_message_history(session)
        print(52)
        # Update system prompt to provide better analysis instructions
        if len(history) > 0 and history[0]["role"] == "system":
            history[0]["content"] = (
                "شما AMN Bot هستید، یک دستیار مفید که URLها را تحلیل می‌کند. هنگامی که داده‌های تحلیل URL از چندین اسکریپت به شما ارائه شود، بینش‌های جامع در مورد موارد زیر ارائه دهید: محتوای وب‌سایت و ساختار آن، جنبه‌های فنی (زمان پاسخ، کدهای وضعیت و غیره)، عناصر SEO (متادیتا، سرتیترها، لینک‌ها)، و هر یافته قابل توجه یا توصیه‌ای. مختصر، عملی و قابل اجرا باشید و به داده‌های مرتبط از نتایج اسکریپت‌ها ارجاع دهید (استناد کنید)."
            )
        
        payload = {
            "model": model_name,
            "messages": history,
            "temperature": temperature,
            "enable_thinking" : False 
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        print(172)
        print("payload is : +?> ",payload)
        print("headers is : +?> ",headers)
        print("base_url is : +?> ",base_url)
        response = requests.post(
            f"{base_url}/chat/completions" ,
            json=payload,
            headers=headers,
            timeout=500,  # Longer timeout for AI processing
        )
        print("answer from model is : +?> ",response.json())
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices")
        if not choices:
            raise ValueError("Groq API returned an empty response.")
        return choices[0]["message"]["content"]

    def _build_message_history(self, session: ChatSession) -> List[dict]:
        system_prompt = {
            "role": "system",
            "content": (
                "تو یک دستیار هوشمند پیدا کردن آسیب پذیری برنامه های تحت وب هستی . با اطلاعات اراعه شده سعی کن آسیب پذیری ها و باگ های موجود رو کامل پیدا کنی و راهکار های مقابله باهاشون رو به فارسی بگی "
            ),
        }
        history = [system_prompt]
        latest_messages = list(session.messages.order_by("created_at", "id").all())
        for message in latest_messages[-10:]:
            history.append({"role": message.role, "content": message.content})
        return history


class ChatSessionDetailView(APIView):
    """Return the stored messages for a session."""

    def get(self, request, session_id):
        session = get_object_or_404(ChatSession, id=session_id)
        serializer = ChatSessionSerializer(session)
        return Response(serializer.data)
