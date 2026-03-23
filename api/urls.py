# api/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ProductViewSet, TryOnViewSet

router = DefaultRouter()
router.register(r'products', ProductViewSet)
router.register(r'tryon', TryOnViewSet)

urlpatterns = [
    path('', include(router.urls)),
]