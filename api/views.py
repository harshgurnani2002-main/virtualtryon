# api/views.py
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from .models import Product, TryOn
from .serializers import ProductSerializer, TryOnSerializer
from .vertex_service import generate_tryon
import os
import threading
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


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
        Returns 202 immediately, processes in background thread.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tryon = serializer.save(status='processing')

        # Process in background thread (non-blocking)
        threading.Thread(
            target=self._process_tryon,
            args=[tryon.id],
            daemon=True
        ).start()

        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)

    def _process_tryon(self, tryon_id):
        """Background processing for virtual try-on"""
        try:
            tryon = TryOn.objects.get(id=tryon_id)

            # Get absolute file paths from MEDIA_ROOT
            person_path  = os.path.join(settings.MEDIA_ROOT, str(tryon.person_image))
            garment_path = os.path.join(settings.MEDIA_ROOT, str(tryon.product.image))

            logger.info(
                f"[TryOn {tryon_id}] Starting – person={person_path}, garment={garment_path}"
            )

            # Call Vertex AI (REST API with base64 images)
            result = generate_tryon(person_path, garment_path)

            if result['success']:
                tryon.result      = result['result_path']
                tryon.status      = 'completed'
                tryon.completed_at = timezone.now()
                logger.info(f"[TryOn {tryon_id}] Completed → {result['result_path']}")
            else:
                tryon.status = 'failed'
                # Log the actual Vertex AI error so it's easy to debug
                logger.error(f"[TryOn {tryon_id}] Failed – {result['error']}")
                print(f"[TryOn {tryon_id}] ERROR: {result['error']}")

            tryon.save()

        except Exception as e:
            TryOn.objects.filter(id=tryon_id).update(status='failed')
            logger.exception(f"[TryOn {tryon_id}] Unhandled exception: {e}")
            print(f"[TryOn {tryon_id}] Unhandled exception: {e}")