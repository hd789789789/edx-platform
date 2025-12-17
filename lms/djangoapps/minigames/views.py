import hashlib
import hmac
import json

from django.conf import settings
from django.utils import timezone
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from openedx.core.lib.api.authentication import BearerAuthenticationAllowInactiveUser
from rest_framework import permissions
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
import math

from .models import MinigameLog
from .serializers import MinigameHighScoreSerializer, MinigameLogSerializer, MinigameUserStatsSerializer


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
    msg = json.dumps(base, sort_keys=True,
                     separators=(',', ':')).encode('utf-8')
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


class MinigameHighScoreView(APIView):
    """
    Trả về điểm cao nhất của từng user cho từng minigame.
    - GET /api/minigames/highscores/
    - GET /api/minigames/highscores/?gameKey=<key>
    Dùng cho leaderboard nên user thường cũng xem được toàn bộ.
    """

    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        game_key = request.query_params.get('gameKey')
        queryset = MinigameLog.objects.filter(msgtype='RESULT')

        if game_key:
            queryset = queryset.filter(payload__gameKey=game_key)

        highscores = {}
        for log in queryset.iterator():
            payload = log.payload or {}
            gkey = payload.get('gameKey')
            if not gkey:
                continue

            score_raw = payload.get('score')
            if score_raw is None:
                score_raw = payload.get('bestScore')
            if score_raw is None:
                score_raw = payload.get('lastScore')

            try:
                score_val = float(score_raw)
            except (TypeError, ValueError):
                continue

            key = (log.user, gkey)
            existing = highscores.get(key)
            if (
                existing is None
                or score_val > existing['best_score']
                or (score_val == existing['best_score'] and log.tsms > existing['last_updated'])
            ):
                highscores[key] = {
                    'user': log.user,
                    'gameKey': gkey,
                    'best_score': score_val,
                    'username': payload.get('username'),
                    'email': payload.get('email'),
                    'last_updated': log.tsms,
                }

        data = list(highscores.values())
        data.sort(
            key=lambda item: (-item['best_score'], item['gameKey'], item['user']))

        serializer = MinigameHighScoreSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class MinigameUserStatsView(APIView):
    """
    Trả về thống kê tổng hợp cho user hiện tại:
    - total_xp: Tổng XP từ tất cả minigames (tổng best_score)
    - total_coins: Tổng coins (bằng total_xp)
    - level: Cấp độ hiện tại
    - xp_current: XP đã đạt được trong level hiện tại
    - xp_required: XP cần để lên level tiếp theo

    Công thức level:
    - LV0 → LV1: 100XP
    - LV1 → LV2: 200XP
    - LV(N) → LV(N+1): (N+1) * 100 XP
    - Tổng XP để đạt level L = 50 * L * (L+1)

    GET /api/minigames/user-stats/
    """

    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)

    def _calculate_level(self, total_xp):
        """
        Tính level và XP hiện tại từ tổng XP.
        Công thức: Tổng XP để đạt level L = 50 * L * (L+1)
        """
        if total_xp <= 0:
            return {
                'level': 0,
                'xp_current': 0,
                'xp_required': 100,  # Cần 100 XP để lên level 1
            }

        # Giải phương trình 50 * L * (L+1) <= total_xp
        # L^2 + L - total_xp/50 <= 0
        # L = (-1 + sqrt(1 + 4*total_xp/50)) / 2 = (-1 + sqrt(1 + total_xp/12.5)) / 2
        discriminant = 1 + total_xp / 12.5
        level = int((-1 + math.sqrt(discriminant)) / 2)

        # XP đã dùng để đạt level hiện tại
        xp_for_current_level = 50 * level * (level + 1)

        # XP đã tích lũy trong level hiện tại
        xp_current = int(total_xp - xp_for_current_level)

        # XP cần để lên level tiếp theo = (level + 1) * 100
        xp_required = (level + 1) * 100

        return {
            'level': level,
            'xp_current': xp_current,
            'xp_required': xp_required,
        }

    def get(self, request):
        user = request.user
        user_str = str(user.id) if user and user.is_authenticated else ''

        if not user_str:
            return Response({
                'total_xp': 0,
                'total_coins': 0,
                'level': 0,
                'xp_current': 0,
                'xp_required': 100,
            })

        # Lấy tất cả RESULT logs của user
        queryset = MinigameLog.objects.filter(user=user_str, msgtype='RESULT')

        # Tính high score cho mỗi game
        highscores = {}
        for log in queryset.iterator():
            payload = log.payload or {}
            gkey = payload.get('gameKey')
            if not gkey:
                continue

            score_raw = payload.get('score')
            if score_raw is None:
                score_raw = payload.get('bestScore')
            if score_raw is None:
                score_raw = payload.get('lastScore')

            try:
                score_val = float(score_raw)
            except (TypeError, ValueError):
                continue

            existing = highscores.get(gkey)
            if existing is None or score_val > existing:
                highscores[gkey] = score_val

        # Tổng XP = tổng tất cả high scores
        total_xp = int(sum(highscores.values()))

        # Coins = XP (có thể đổi công thức sau nếu cần)
        total_coins = total_xp

        # Tính level
        level_info = self._calculate_level(total_xp)

        data = {
            'total_xp': total_xp,
            'total_coins': total_coins,
            'level': level_info['level'],
            'xp_current': level_info['xp_current'],
            'xp_required': level_info['xp_required'],
        }

        serializer = MinigameUserStatsSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)
