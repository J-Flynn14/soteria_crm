from .models import Candidate, Contact, Job, Application, Placement, Company
from rest_framework import serializers


class CandidateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Candidate
        fields = '__all__'  

class CompanySerializer(serializers.ModelSerializer):
    class Meta:
        model = Company
        fields = '__all__'

class ContactSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contact
        fields = '__all__'

class JobSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = '__all__' 

class ApplicationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = '__all__'

class PlacementSerializer(serializers.ModelSerializer):
    class Meta:
        model = Placement
        fields = '__all__'

class CVUploadSerializer(serializers.Serializer):
    cv_file = serializers.FileField()

class BulkCVUploadSerializer(serializers.Serializer):
    cv_files = serializers.ListField(child=serializers.FileField())