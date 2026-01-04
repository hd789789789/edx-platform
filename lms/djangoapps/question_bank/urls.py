from django.urls import path
from .views import (
    QuestionBankListCreateAPIView,
    QuestionBankRetrieveUpdateDeleteAPIView,
)

urlpatterns = [
    path("", QuestionBankListCreateAPIView.as_view(), name="question_bank_list_create"),
    path("<str:code>/", QuestionBankRetrieveUpdateDeleteAPIView.as_view(), name="question_bank_rud_by_code"),
]


