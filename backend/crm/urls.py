from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import *

# Initialize the router
router = DefaultRouter()
router.register(r'candidates', CandidateViewSet)
router.register(r'companies', CompanyViewSet)
router.register(r'contacts', ContactViewSet)
router.register(r'jobs', JobViewSet)
router.register(r'applications', ApplicationViewSet)
router.register(r'placements', PlacementViewSet)

# URL patterns
urlpatterns = [
    path('api/', include(router.urls)),
    path('trigger_anonymise_cv/', trigger_anonymise_cv, name='trigger_anonymise_cv'),
    path('trigger_screening/', trigger_screening, name='trigger_screening'),
    path('trigger_cleanup_database/', trigger_cleanup_database, name='trigger_cleanup_database'),
    path('trigger_delete_orphaned_files/', trigger_delete_orphaned_files, name='trigger_delete_orphaned_files'),
    path('trigger_send_screening_form/', trigger_send_screening_form, name='trigger_send_screening_form'),
    path('trigger_candidate_from_cv/', TriggerCandidateFromCV.as_view(), name='trigger_candidate_from_cv'),
    path('trigger_check_api_connection/', trigger_check_api_connection, name='trigger_check_api_connection'),
]
