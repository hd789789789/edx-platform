from rest_framework import serializers

from .models import MinigameLog, QuestionPool


class MinigameLogSerializer(serializers.ModelSerializer):
    """
    Serializer để expose đúng cấu trúc:
    {
        "msgid": ...,
        "msgtype": "...",
        "key": "...",
        "tsms": ...,
        "user": "...",
        "payload": {...}
    }
    """

    # Các field nhạy cảm được generate server-side, client chỉ đọc
    key = serializers.CharField(read_only=True)
    user = serializers.CharField(read_only=True)

    class Meta:
        model = MinigameLog
        fields = ('msgid', 'msgtype', 'key', 'tsms', 'user', 'payload')
        read_only_fields = ('msgid', 'key', 'user')


class MinigameHighScoreSerializer(serializers.Serializer):
    """
    Serializer cho dữ liệu high score đã được tính sẵn.
    """

    user = serializers.CharField()
    gameKey = serializers.CharField()
    best_score = serializers.FloatField()
    username = serializers.CharField(allow_null=True, required=False)
    email = serializers.EmailField(allow_null=True, required=False)
    last_updated = serializers.IntegerField()


class MinigameUserStatsSerializer(serializers.Serializer):
    """
    Serializer cho thống kê tổng hợp của user.
    """

    total_xp = serializers.IntegerField()
    total_coins = serializers.IntegerField()
    level = serializers.IntegerField()
    xp_current = serializers.IntegerField()
    xp_required = serializers.IntegerField()


class QuestionPoolSerializer(serializers.ModelSerializer):
    """
    Serializer cho QuestionPool model.
    """

    class Meta:
        model = QuestionPool
        fields = ('mate_id', 'cat_list', 'mate_meta', 'mate_content', 'status')


class QuestionPoolMateIdSerializer(serializers.Serializer):
    """
    Serializer chỉ trả về mate_id cho API lấy danh sách tất cả mate_id.
    """

    mate_id = serializers.CharField()
