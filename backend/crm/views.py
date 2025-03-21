from .models import Candidate, Contact, Job, Application, Placement, Company
from django.core.files.storage import default_storage
from django.core.cache import cache
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework import viewsets, generics, status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.db import transaction
from .forms import CandidateForm
from django.conf import settings
from django.utils.crypto import get_random_string
import logging
import os

from .serializers import (
    CandidateSerializer, ContactSerializer, JobSerializer,
    ApplicationSerializer, PlacementSerializer, CompanySerializer,
    BulkCVUploadSerializer, CVUploadSerializer
)
from .tasks import (
    process_screening,
    process_anonymise_cv,
    cleanup_database,
    delete_orphaned_files,
    send_screening_form,
    process_candidate_from_cv,
    process_test_api_connection,
    update_geolocation_from_address,
)

logger = logging.getLogger(__name__)

##################
# Model ViewSets #
##################

class CandidateViewSet(viewsets.ModelViewSet):
    queryset = Candidate.objects.all()
    serializer_class = CandidateSerializer
    parser_classes = (MultiPartParser, FormParser)

class CompanyViewSet(viewsets.ModelViewSet):
    queryset = Company.objects.all()
    serializer_class = CompanySerializer

class ContactViewSet(viewsets.ModelViewSet):
    queryset = Contact.objects.all()
    serializer_class = ContactSerializer

class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all()
    serializer_class = JobSerializer

class ApplicationViewSet(viewsets.ModelViewSet):
    queryset = Application.objects.all()
    serializer_class = ApplicationSerializer

class PlacementViewSet(viewsets.ModelViewSet):
    queryset = Placement.objects.all()
    serializer_class = PlacementSerializer

@api_view(['POST'])
def trigger_anonymise_cv(request):
    candidate_id = request.data.get('candidate_id')
    if candidate_id:
        transaction.on_commit(lambda: process_anonymise_cv.delay(candidate_id))
        return Response(
            {"message": f"anonymise cv task initiated for candidate {candidate_id}."},
            status=status.HTTP_202_ACCEPTED
        )
    return Response({"error": "candidate_id not provided"}, status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
def trigger_screening(request):
    candidate_id = request.data.get('candidate_id')
    if candidate_id:
        try:
            candidate = Candidate.objects.get(id=candidate_id)
            transaction.on_commit(lambda: process_screening.delay(candidate.id, cv_text=None))
            return Response(
                {"message": f"Screening task initiated for candidate {candidate_id}."},
                status=status.HTTP_202_ACCEPTED
            )
        except Candidate.DoesNotExist:
            return Response({"error": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response({"error": "candidate_id not provided"}, status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
def trigger_send_screening_form(request):
    candidate_id = request.data.get('candidate_id')
    if candidate_id:
        try:
            transaction.on_commit(lambda: send_screening_form.delay(candidate_id))
            return Response({"message": "send_screening_form task initiated"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"message": f"send_screening_form task not initiated: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response({"error": "candidate_id not provided"}, status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
def trigger_form_submission(request):
    candidate_id = request.data.get('candidate_id')
    if candidate_id:
        try:
            candidate = Candidate.objects.get(id=candidate_id)
            form = CandidateForm(request.data)
            if form.is_valid():
                candidate.form_results = form.cleaned_data
                candidate.save(update_fields=["form_results"])
                return Response({"message": "Form submitted successfully."}, status=status.HTTP_202_ACCEPTED)
            else:
                return Response(form.errors, status=status.HTTP_400_BAD_REQUEST)
        except Candidate.DoesNotExist:
            return Response({"error": "Candidate not found."}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response({"message": f"Form submission failed: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return Response({"error": "candidate_id not provided"}, status=status.HTTP_204_NO_CONTENT)

@api_view(['POST'])
def trigger_cleanup_database(request):
    try:
        transaction.on_commit(lambda: cleanup_database.delay())
        return Response({"message": "cleanup_database task initiated"}, status=status.HTTP_202_ACCEPTED)
    except Exception as e:
        return Response({"message": f"cleanup_database task not initiated: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

@api_view(['POST'])
def trigger_delete_orphaned_files(request):
    try:
        transaction.on_commit(lambda: delete_orphaned_files.delay())
        return Response({"message": "delete_orphaned_files task initiated"}, status=status.HTTP_202_ACCEPTED)
    except Exception as e:
        return Response({"message": f"delete_orphaned_files task not initiated: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

""" class TriggerCandidateFromCV(generics.CreateAPIView):
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = CVUploadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cv_file = serializer.validated_data['cv_file']
        try:
            file_bytes = cv_file.read()
            transaction.on_commit(lambda: process_candidate_from_cv.delay(file_bytes))
            return Response({"message": "candidate_from_cv task initiated"}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            return Response({"message": f"candidate_from_cv task not initiated: {e}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR) """
        
class TriggerCandidateFromCV(generics.CreateAPIView):
    parser_classes = (MultiPartParser, FormParser)
    serializer_class = BulkCVUploadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cv_files = serializer.validated_data['cv_files']

        uploads_dir = 'temp_cv_uploads'
        full_uploads_dir = os.path.join(settings.MEDIA_ROOT, uploads_dir)
        os.makedirs(full_uploads_dir, exist_ok=True)

        for cv_file in cv_files:
            dest_filename = f"{cv_file.name}"
            dest_path = os.path.join(full_uploads_dir, dest_filename)

            try:
                if hasattr(cv_file, 'temporary_file_path'):
                    src_path = cv_file.temporary_file_path()
                    shutil.move(src_path, dest_path)
                else:
                    with open(dest_path, 'wb') as out_file:
                        for chunk in cv_file.chunks():
                            out_file.write(chunk)
            except Exception as e:
                return Response(
                    {"error": f"Error saving file {cv_file.name}: {e}"},status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            transaction.on_commit(lambda dest_path=dest_path: process_candidate_from_cv.delay(dest_path))
        return Response({"message": "CV processing tasks initiated"}, status=status.HTTP_202_ACCEPTED)

@api_view(['GET'])
def trigger_check_api_connection(request):
    transaction.on_commit(lambda: process_test_api_connection.delay())
    return Response({"message": "API connection check task initiated"}, status=status.HTTP_202_ACCEPTED)