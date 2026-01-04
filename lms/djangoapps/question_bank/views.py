from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from django.shortcuts import get_object_or_404

from .models import QuestionBank
from .serializers import QuestionBankSerializer


class QuestionBankListCreateAPIView(APIView):
    """
    GET: list all or if ?code=... given, return the single item
    POST: create new question
    """
    permission_classes = (AllowAny,)

    def get(self, request):
        code = request.GET.get("code")
        if code:
            obj = get_object_or_404(QuestionBank, code=code)
            serializer = QuestionBankSerializer(obj)
            return Response(serializer.data)
        queryset = QuestionBank.objects.all()
        serializer = QuestionBankSerializer(queryset, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = QuestionBankSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class QuestionBankRetrieveUpdateDeleteAPIView(generics.GenericAPIView):
    """
    PUT /api/question_bank/<code>/  -> update by code
    DELETE /api/question_bank/<code>/ -> delete by code
    """
    serializer_class = QuestionBankSerializer
    permission_classes = (AllowAny,)
    lookup_field = "code"

    def get_object(self):
        code = self.kwargs.get("code")
        return get_object_or_404(QuestionBank, code=code)

    def put(self, request, code):
        obj = self.get_object()
        serializer = self.get_serializer(obj, data=request.data, partial=False)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def patch(self, request, code):
        obj = self.get_object()
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, code):
        obj = self.get_object()
        obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


