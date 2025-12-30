import hashlib
import hmac
import json

from django.conf import settings
from django.utils import timezone
from edx_rest_framework_extensions.auth.session.authentication import SessionAuthenticationAllowInactiveUser
from openedx.core.lib.api.authentication import BearerAuthenticationAllowInactiveUser
from rest_framework import permissions, status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
import math

from .models import MinigameLog, QuestionPool
from .serializers import (
    MinigameHighScoreSerializer,
    MinigameLogSerializer,
    MinigameUserStatsSerializer,
    QuestionPoolSerializer,
    QuestionPoolMateIdSerializer,
)


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
        """
        New per-level requirement:
        XP_required(level) = 100 * (level + 1) ** 1.5
        We iterate levels adding required XP until total_xp fits in current level.
        """
        if total_xp <= 0:
            return {
                'level': 0,
                'xp_current': 0,
                'xp_required': int(100 * (1 ** 1.5)),
            }

        level = 0
        cumulative = 0.0
        while True:
            next_req = 100.0 * (level + 1) ** 1.5
            if total_xp < cumulative + next_req:
                xp_current = int(total_xp - cumulative)
                return {
                    'level': level,
                    'xp_current': xp_current,
                    'xp_required': int(next_req),
                }
            cumulative += next_req
            level += 1

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

        # Query param for client/course identification (per plan)
        clientid_param = request.query_params.get('clientid')
        # Normalize/URL-decode clientid_param to match encoded payloads
        try:
            from urllib.parse import unquote
            clientid_param = unquote(
                clientid_param) if clientid_param is not None else None
        except Exception:
            pass

        # Maps to keep highest-score records:
        # xp_highscores: keyed by (appid, clientid) -> payload with highest score
        # coin_highscores: keyed by appid -> payload with highest score
        xp_highscores = {}
        coin_highscores = {}

        for log in queryset.iterator():
            payload = log.payload or {}
            # prefer 'appid', fall back to legacy 'gameKey' if present
            appid = payload.get('appid') or payload.get('gameKey')
            if not appid:
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

            tsms = getattr(log, 'tsms', 0)

            # clientid from payload (may be URL-encoded)
            clientid = payload.get('clientid')
            try:
                if clientid:
                    from urllib.parse import unquote
                    clientid = unquote(clientid)
            except Exception:
                pass

            # For XP (per-course), only include records that match provided clientid_param
            if clientid_param and clientid == clientid_param:
                key_xp = (appid, clientid)
                existing = xp_highscores.get(key_xp)
                if (
                    existing is None
                    or score_val > existing['best_score']
                    or (score_val == existing['best_score'] and tsms > existing['tsms'])
                ):
                    xp_highscores[key_xp] = {
                        'best_score': score_val,
                        'payload': payload,
                        'tsms': tsms,
                    }

            # For coins (system-wide) group only by appid
            existing_coin = coin_highscores.get(appid)
            if (
                existing_coin is None
                or score_val > existing_coin['best_score']
                or (score_val == existing_coin['best_score'] and tsms > existing_coin['tsms'])
            ):
                coin_highscores[appid] = {
                    'best_score': score_val,
                    'payload': payload,
                    'tsms': tsms,
                }

        # Compute totals from payload fields, treating missing values as 0
        total_xp = int(
            sum(
                int((entry['payload'].get('xp') or 0) +
                    (entry['payload'].get('bonus_xp') or 0))
                for entry in xp_highscores.values()
            )
        )

        total_coins = int(
            sum(
                int((entry['payload'].get('coin') or 0) +
                    (entry['payload'].get('bonus_coin') or 0))
                for entry in coin_highscores.values()
            )
        )

        # Tính level dùng công thức mới
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


class QuestionPoolMateIdListView(APIView):
    """
    API lấy danh sách tất cả mate_id.

    GET /api/minigames/question-pool/mate-ids/
    """

    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request):
        """
        Trả về danh sách tất cả mate_id với status != 0 (không bị xóa).
        """
        mate_ids = QuestionPool.objects.filter(
            status__gt=0).values_list('mate_id', flat=True)
        data = [{'mate_id': mate_id} for mate_id in mate_ids]

        serializer = QuestionPoolMateIdSerializer(data=data, many=True)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.data)


class QuestionPoolListCreateView(ListCreateAPIView):
    """
    List hoặc tạo question pool entry.

    GET  /api/minigames/question-pool/        -> danh sách tất cả (hoặc theo mate_id nếu có query param)
    POST /api/minigames/question-pool/        -> tạo entry mới
    """

    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = QuestionPoolSerializer
    pagination_class = None

    def get_queryset(self):
        queryset = QuestionPool.objects.filter(
            status__gt=0)  # Chỉ lấy những entry chưa bị xóa

        # Nếu có query param mate_id, filter theo mate_id
        mate_id = self.request.query_params.get('mate_id')
        if mate_id:
            queryset = queryset.filter(mate_id=mate_id)

        return queryset

    def perform_create(self, serializer):
        """
        Khi tạo mới: nếu có record cùng `mate_id` đã bị soft-delete (status == 0)
        thì tái sử dụng record đó (cập nhật các field và set status theo request),
        tránh lỗi duplicate key trên primary key.
        Nếu record tồn tại và status > 0 thì trả về ValidationError.
        """
        mate_id = serializer.validated_data.get('mate_id')
        if not mate_id:
            # Không có mate_id thì fallback tạo bình thường (sẽ bị validate fail nếu model yêu cầu)
            serializer.save()

    def create(self, request, *args, **kwargs):
        """
        Override create to handle case where mate_id exists but is soft-deleted.
        We must check for existing soft-deleted record before running serializer validation
        (which would raise uniqueness error). If found and status==0, perform update.
        """
        mate_id = request.data.get('mate_id')
        if mate_id:
            try:
                existing = QuestionPool.objects.get(mate_id=mate_id)
                # If exists and soft-deleted -> update and return
                if existing.status == 0:
                    serializer = self.get_serializer(
                        existing, data=request.data)
                    serializer.is_valid(raise_exception=True)
                    serializer.save()
                    return Response(serializer.data, status=status.HTTP_200_OK)
                else:
                    from rest_framework.exceptions import ValidationError

                    raise ValidationError(
                        {'mate_id': ['question pool có mate id đã tồn tại.']})
            except QuestionPool.DoesNotExist:
                # Not exists -> proceed to normal create flow
                pass

        return super().create(request, *args, **kwargs)
        pass


class QuestionPoolDetailView(RetrieveUpdateDestroyAPIView):
    """
    Xem / sửa / xoá question pool entry theo mate_id.

    GET    /api/minigames/question-pool/{mate_id}/
    PUT    /api/minigames/question-pool/{mate_id}/
    PATCH  /api/minigames/question-pool/{mate_id}/
    DELETE /api/minigames/question-pool/{mate_id}/
    """

    authentication_classes = (
        BearerAuthenticationAllowInactiveUser,
        SessionAuthenticationAllowInactiveUser,
    )
    permission_classes = (permissions.IsAuthenticated,)
    serializer_class = QuestionPoolSerializer
    lookup_field = 'mate_id'

    def get_queryset(self):
        # Chỉ lấy những entry chưa bị xóa
        return QuestionPool.objects.filter(status__gt=0)

    def perform_destroy(self, instance):
        """
        Thực hiện soft delete bằng cách set status = 0 thay vì xóa thật.
        """
        instance.status = 0
        instance.save()

    def destroy(self, request, *args, **kwargs):
        """
        Override default destroy to return a success message after soft-delete.
        """
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response({'detail': 'Successfully'})
