"""
Serializers for Learner Chat API
"""
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import ChatRoom, ChatMessage

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user information in chat"""
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'display_name')
        read_only_fields = ('id', 'username', 'display_name')

    def get_display_name(self, obj):
        try:
            return obj.profile.name if obj.profile.name else obj.username
        except:
            return obj.username


class ChatMessageSerializer(serializers.ModelSerializer):
    """Serializer for chat messages"""
    user = UserSerializer(read_only=True)
    mentions = UserSerializer(many=True, read_only=True)
    mention_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    can_delete = serializers.SerializerMethodField()

    class Meta:
        model = ChatMessage
        fields = (
            'id', 'user', 'message', 'mentions', 'mention_ids',
            'is_deleted', 'created_at', 'can_delete'
        )
        read_only_fields = ('id', 'user', 'mentions', 'is_deleted', 'created_at', 'can_delete')

    def get_can_delete(self, obj):
        """Check if current user can delete this message"""
        request = self.context.get('request')
        if not request or not request.user:
            return False
        
        # Admin can delete any message
        if request.user.is_staff:
            return True
        
        # Users can only delete their own messages
        return obj.user == request.user



class ChatRoomSerializer(serializers.ModelSerializer):
    """Serializer for chat rooms"""
    messages = ChatMessageSerializer(many=True, read_only=True)
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ('id', 'course_id', 'chat_type', 'messages', 'message_count', 'created_at')
        read_only_fields = ('id', 'created_at')

    def get_message_count(self, obj):
        return obj.messages.filter(is_deleted=False).count()

