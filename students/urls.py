# students/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import StudentViewSet

router = DefaultRouter()
router.register(r'students', StudentViewSet, basename='student')

# Custom URL patterns for additional functionality
urlpatterns = [
    path('', include(router.urls)),
    
    # Additional endpoints (they're already in the ViewSet, but you can add custom ones if needed)
    # These are automatically available through the router, but if you want explicit URLs:
    # path('students/bulk_send_sms/', StudentViewSet.as_view({'post': 'bulk_send_sms'}), name='student-bulk-send-sms'),
    # path('students/sms_balance/', StudentViewSet.as_view({'get': 'sms_balance'}), name='student-sms-balance'),
]