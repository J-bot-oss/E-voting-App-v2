from rest_framework import generics
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsAdminUser
from audit.models import AuditLog
from audit.serializers import AuditLogSerializer
from audit.services import AuditService


class AuditLogListView(generics.ListAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        queryset = AuditLog.objects.order_by("-timestamp")

        action = self.request.query_params.get("action")
        if action:
            queryset = queryset.filter(action=action.strip())

        user = self.request.query_params.get("user")
        if user:
            queryset = queryset.filter(user_identifier__icontains=user.strip())

        return queryset


class AuditActionTypesView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        action_types = list(AuditService.get_action_types())
        return Response(action_types)