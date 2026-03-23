from rest_framework import serializers

from audit.models import AuditLog


class AuditLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditLog
        fields = ["id", "timestamp", "action", "user_identifier", "details"]
        read_only_fields = ["id", "timestamp", "action", "user_identifier", "details"]