# api/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Product, TryOn
from .serializers import ProductSerializer, TryOnSerializer
from .vertex_service import generate_tryon
import os
from django.conf import settings
from django.utils import timezone


class ProductViewSet(viewsets.ModelViewSet):
    """Product CRUD - local image upload"""
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    parser_classes = [MultiPartParser, FormParser]


class TryOnViewSet(viewsets.ModelViewSet):
    """Virtual Try-On - local upload, cloud generation"""
    queryset = TryOn.objects.all()
    serializer_class = TryOnSerializer
    parser_classes = [MultiPartParser, FormParser]

    def create(self, request, *args, **kwargs):
        """
        Upload person image + select product.
        Synchronously processes the virtual try-on and returns the final URL.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tryon = serializer.save(status='processing')

        try:
            # Get absolute file paths from MEDIA_ROOT
            person_path  = os.path.join(settings.MEDIA_ROOT, str(tryon.person_image))
            garment_path = os.path.join(settings.MEDIA_ROOT, str(tryon.product.image))

            print(f"[{timezone.now()}] [TryOn {tryon.id}] Starting API Process – person={person_path}, garment={garment_path}")

            # Call Vertex AI (REST API with base64 images)
            result = generate_tryon(person_path, garment_path)

            if result.get('success'):
                # Save just the URL instead of local path
                tryon.result      = result['result_url']
                tryon.status      = 'completed'
                tryon.completed_at = timezone.now()
                print(f"[{timezone.now()}] [TryOn {tryon.id}] Completed → {result['result_url']}")
                tryon.save()

                # Return exactly what the user requested
                return Response({
                    "id": tryon.id,
                    "product_id": tryon.product.id,
                    "output_image_url": tryon.result,
                    "status": tryon.status
                }, status=status.HTTP_200_OK)
            else:
                tryon.status = 'failed'
                print(f"[{timezone.now()}] [TryOn {tryon.id}] ERROR: {result.get('error')}")
                tryon.save()
                return Response({"error": result.get('error')}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        except Exception as e:
            tryon.status = 'failed'
            tryon.save()
            print(f"[{timezone.now()}] [TryOn {tryon.id}] Unhandled exception: {e}")
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)