# api/models.py
from django.db import models
import uuid

class Product(models.Model):
    name = models.CharField(max_length=200)
    image = models.ImageField(upload_to='products/')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class TryOn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    person_image = models.ImageField(upload_to='person/')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    result = models.URLField(blank=True, null=True)
    status = models.CharField(
        max_length=20, 
        default='pending',
        choices=[
            ('pending', 'Pending'),
            ('processing', 'Processing'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return str(self.id)