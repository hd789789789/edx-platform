from rest_framework import serializers

from .models import MinigameLog


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


