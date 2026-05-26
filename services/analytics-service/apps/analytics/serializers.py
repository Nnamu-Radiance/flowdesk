from rest_framework import serializers


class DashboardSerializer(serializers.Serializer):
    total_workflows = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()
    pending = serializers.IntegerField()


class MetricItemSerializer(serializers.Serializer):
    label = serializers.CharField()
    value = serializers.FloatField()
