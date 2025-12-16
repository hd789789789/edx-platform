from django.urls import path

from .views import MinigameLogDetailView, MinigameLogListCreateView

app_name = 'minigames'

urlpatterns = [
    path('logs/', MinigameLogListCreateView.as_view(), name='minigame_log_list'),
    path('logs/<int:msgid>/', MinigameLogDetailView.as_view(), name='minigame_log_detail'),
]


