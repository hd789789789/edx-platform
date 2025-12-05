"""
URLs for Learner Chat API
"""
from django.conf import settings
from django.urls import re_path
from .views import ChatRoomViewSet

viewset = ChatRoomViewSet.as_view({
    'get': 'list_messages',
    'post': 'create_message',
})

delete_message_view = ChatRoomViewSet.as_view({
    'delete': 'delete_message',
})

urlpatterns = [
    re_path(
        fr'^{settings.COURSE_KEY_PATTERN}/(?P<chat_type>general|qa|technical)/messages/$',
        viewset,
        name='chat-messages'
    ),
    re_path(
        fr'^{settings.COURSE_KEY_PATTERN}/(?P<chat_type>general|qa|technical)/messages/(?P<message_id>\d+)/$',
        delete_message_view,
        name='chat-delete-message'
    ),
]

