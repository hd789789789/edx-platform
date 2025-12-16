import hashlib
import hmac
import json

from django.conf import settings
from django.utils import timezone
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from openedx.core.lib.api.authentication import BearerAuthenticationAllowInactiveUser
from rest_framework import permissions
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView

from .models import MinigameLog
from .serializers import MinigameLogSerializer


def _generate_key(user_str: str, tsms: int, payload) -> str:
    """
    Sinh hash key để lưu trong DB nhằm verify request.
    Key dựa trên SECRET_KEY + user + tsms + payload.
    """
    secret = settings.SECRET_KEY.encode('utf-8')
    base = {
        'user': user_str,
        'tsms': tsms,
        'payload': payload,
    }
    msg = json.dumps(base, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


class MinigameLogListCreateView(ListCreateAPIView):
    """
    List hoặc tạo log cho user hiện tại.

    GET  /api/minigames/logs/        -> danh sách log của user hiện tại
    POST /api/minigames/logs/        -> tạo log mới
    """

    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = MinigameLogSerializer
    pagination_class = None  # Trả về list JSON đơn giản cho frontend

    def get_queryset(self):
        user = self.request.user
        user_str = str(user.id) if user and user.is_authenticated else ''
        return MinigameLog.objects.filter(user=user_str)

    def perform_create(self, serializer):
        """
        - Lấy user từ request.user
        - Auto-fill tsms nếu client không gửi
        - Sinh key HMAC và lưu xuống DB
        """
        user = self.request.user
        user_str = str(user.id) if user and user.is_authenticated else ''

        data = serializer.validated_data
        tsms = data.get('tsms')
        if not tsms:
            tsms = int(timezone.now().timestamp() * 1000)
            data['tsms'] = tsms

        payload = data.get('payload') or {}
        key = _generate_key(user_str, tsms, payload)

        serializer.save(user=user_str, key=key)


class MinigameLogDetailView(RetrieveUpdateDestroyAPIView):
    """
    Xem / sửa / xoá 1 log cụ thể của user hiện tại.

    GET    /api/minigames/logs/{msgid}/
    PUT    /api/minigames/logs/{msgid}/
    PATCH  /api/minigames/logs/{msgid}/
    DELETE /api/minigames/logs/{msgid}/
    """

    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = MinigameLogSerializer
    lookup_field = 'msgid'

    def get_queryset(self):
        user = self.request.user
        user_str = str(user.id) if user and user.is_authenticated else ''
        return MinigameLog.objects.filter(user=user_str)


