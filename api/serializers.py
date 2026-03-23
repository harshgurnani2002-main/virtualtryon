from rest_framework import serializers
from .models import Product, TryOn


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'image', 'created_at']
        read_only_fields = ['id', 'created_at']

class TryOnSerializer(serializers.ModelSerializer):
    result = serializers.URLField(read_only=True)

    class Meta:
        model = TryOn
        fields = ['id', 'person_image', 'product', 'result', 'status', 'created_at', 'completed_at']
        read_only_fields = ['id', 'result', 'status', 'created_at', 'completed_at']