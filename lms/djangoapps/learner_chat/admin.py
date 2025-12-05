"""
Django Admin for Learner Chat
"""
from django.contrib import admin
from .models import ChatRoom, ChatMessage


@admin.register(ChatRoom)
class ChatRoomAdmin(admin.ModelAdmin):
    list_display = ('course_id', 'chat_type', 'created_at', 'updated_at')
    list_filter = ('chat_type', 'created_at')
    search_fields = ('course_id',)


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ('user', 'room', 'message_preview', 'is_deleted', 'created_at')
    list_filter = ('is_deleted', 'created_at', 'room__chat_type')
    search_fields = ('message', 'user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    filter_horizontal = ('mentions',)

    def message_preview(self, obj):
        return obj.message[:100] + '...' if len(obj.message) > 100 else obj.message
    message_preview.short_description = 'Message Preview'

