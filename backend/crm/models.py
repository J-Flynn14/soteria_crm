from django.core.validators import FileExtensionValidator
from django.contrib.gis.db import models as gis_models
from django.contrib.postgres.fields import ArrayField
from django.db import models
from .file_utils import get_file_upload_to
import logging

logger = logging.getLogger(__name__)

class Candidate(models.Model):
    SCREENING_CHOICES = [
        ('Not Screened', 'Not Screened'),
        ('Qualified - RM', 'Qualified - RM'),
        ('Qualified - DM', 'Qualified - DM'),
        ('Qualified - TL', 'Qualified - TL'),
        ('Qualified - SRSW','Qualified - SRSW'),
        ('Qualified - RSW','Qualified - RSW'),
        ('Intermediate', 'Intermediate'),
        ('Unqualified','Unqualified'),
        ('Unqualified - Out of country', 'Unqualified - Out of country'),
        ('Unqualified - NSFW', 'Unqualified - NSFW'),
    ]
    
    FORM_STATUS_CHOICES = [
        ('Not Sent', 'Not Sent'),
        ('Pending', 'Pending'),
        ('Submitted', 'Submitted'),
    ]

    EXPLICIT_FIELD_MAPPING = {
            'roles_interested': 'roles_interested',
            'uk_drivers_licence': 'uk_drivers_licence',
            'postcode': 'postcode',
            'notice_period': 'notice_period',
            'qualifications': 'qualifications',
            'experience': 'experience',
            'commute_time': 'commute_time',
            'availability_shifts': 'availability_shifts',
            'current_dbs': 'current_dbs',
            'current_salary': 'current_salary',
            'convictions': 'convictions',
            'desired_hourly_rate': 'desired_hourly_rate',
            'companies_excluded': 'companies_excluded',
            'share_cv': 'share_cv',
        }

    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    mobile_num = models.CharField(max_length=30, unique=True, blank=True, null=True)
    email = models.EmailField(unique=True)
    address = models.CharField(max_length=255)
    postcode = models.CharField(max_length=50, null=True, blank=True)
    position = models.CharField(max_length=255, blank=True, null=True)
    employer = models.CharField(max_length=255, blank=True, null=True)
    
    roles_interested = ArrayField(models.CharField(max_length=100, null=True, blank=True),default=list,blank=True,null=True)
    uk_drivers_licence = models.CharField(max_length=50, null=True, blank=True)
    notice_period = models.CharField(max_length=100, null=True, blank=True)
    qualifications = ArrayField(models.CharField(max_length=100, null=True, blank=True),default=list,blank=True,null=True)
    experience = ArrayField(models.CharField(max_length=100, blank=True),default=list,blank=True,null=True)
    commute_time = models.CharField(max_length=50, null=True, blank=True)
    current_dbs = models.CharField(max_length=100, null=True, blank=True)
    current_salary = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    convictions = models.BooleanField(default=False, null=True, blank=True)
    desired_hourly_rate = models.DecimalField(max_digits=10, decimal_places=2,null=True, blank=True)
    companies_excluded = ArrayField(models.CharField(max_length=100, null=True, blank=True),default=list,blank=True,null=True)
    availability_shifts = models.CharField(max_length=50, null=True, blank=True)
    share_cv = models.CharField(max_length=50, null=True, blank=True)

    cv = models.FileField(upload_to=get_file_upload_to, null=True, blank=True,
                          validators=[FileExtensionValidator(allowed_extensions=['pdf', 'docx', 'txt'])])
    anonymised_cv = models.FileField(upload_to=get_file_upload_to, null=True, blank=True,
                                     validators=[FileExtensionValidator(allowed_extensions=['pdf'])])
    
    form_results = models.JSONField(blank=True, null=True)

    call_log = models.FileField(upload_to=get_file_upload_to, null=True, blank=True,
                                   validators=[FileExtensionValidator(allowed_extensions=['txt'])])
    screening_notes = models.FileField(upload_to=get_file_upload_to, null=True, blank=True,
                          validators=[FileExtensionValidator(allowed_extensions=['txt'])])
    
    screening_status = models.CharField(choices=SCREENING_CHOICES, default='Not Screened')
    form_submission_status = models.CharField(max_length=20, choices=FORM_STATUS_CHOICES, default='Not Sent')

    geolocation = gis_models.PointField(geography=True, null=True, blank=True)

    screening_first_sent = models.DateTimeField(blank=True, null=True)
    screening_second_sent = models.DateTimeField(blank=True, null=True)
    screening_third_sent = models.DateTimeField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=['first_name'], name='idx_candidate_first_name'),
            models.Index(fields=['last_name'], name='idx_candidate_last_name'),
            models.Index(fields=['address'], name='idx_candidate_address'),
            models.Index(fields=['postcode'], name='idx_candidate_postcode'),
            gis_models.Index(fields=['geolocation'], name='idx_candidate_geolocation', condition=models.Q(geolocation__isnull=False)),
            models.Index(fields=['position'], name='idx_candidate_position', condition=models.Q(position__isnull=False)),
        ]

    def __str__(self):
        return self.first_name + self.last_name
    
    def __init__(self, *args, **kwargs):
        # Call parent init and store the original cv.
        super().__init__(*args, **kwargs)
        self._original_cv = self.cv
    
    def save(self, *args, **kwargs):
        if self.pk:
            if self.cv != self._original_cv:
                logger.info(f"[MODEL] CV changed for candidate {self.first_name} {self.last_name}.")
                if self.screening_notes and self.cv:  # assuming notes are present if a file existed
                    self.screening_notes = None
                    self.screening_status = 'Not Screened'
                    logger.info(f"[MODEL] Screening notes cleared and status reset for Candidate {self.pk}.")

        if self.form_results:
            self._process_form_results()
        
        super().save(*args, **kwargs)
        self._original_cv = self.cv

    def _process_form_results(self):
        extra = self.form_results.copy()
        keys_to_extract = set(self.EXPLICIT_FIELD_MAPPING.keys()) & set(extra.keys())
        if keys_to_extract:
            for json_key in keys_to_extract:
                model_field = self.EXPLICIT_FIELD_MAPPING[json_key]
                value = extra.pop(json_key)
                field = self._meta.get_field(model_field)
                if isinstance(field, ArrayField):
                    if isinstance(value, list):
                        value = [str(item).strip() for item in value if str(item).strip()]
                    elif isinstance(value, str):
                        value = [item.strip() for item in value.split(",")] if "," in value else [value.strip()]
                    else:
                        value = [str(value).strip()] if str(value).strip() else []
                setattr(self, model_field, value)
            # Save any remaining extra values back into form_results.
            self.form_results = extra

    """ def _post_save_actions(self):
        from .tasks import process_screening, update_geolocation_from_address
        if not self.geolocation:
            postcode = self.postcode if self.postcode else ""
            update_geolocation_from_address.delay(self.address, postcode)
            logger.info(f"[MODEL] Geolocation update scheduled for Candidate {self.pk}.")
        self.refresh_from_db()
        if self.cv and self.screening_status == "Not Screened":
            process_screening.delay(self.pk, cv_text=None)
            logger.info(f"[MODEL] Screening task scheduled for Candidate {self.pk}.") """

    @classmethod
    def bulk_post_save_actions(cls, candidates):
        for candidate in candidates:
            candidate.refresh_from_db()
            candidate._post_save_actions()
    
class Company(models.Model):
    name = models.CharField(max_length=255)
    industry = models.CharField(max_length=255, blank=True, null=True)
    last_updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['name'], name='idx_company_name'),
            models.Index(fields=['industry'], name='idx_company_industry', condition=models.Q(industry__isnull=False)),
        ]

    def __str__(self):
        return self.name

class Contact(models.Model):
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    position = models.CharField(max_length=255, blank=True, null=True)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, related_name="contacts", null=True)
    email = models.EmailField(unique=True, blank=True, null=True)
    mobile_num = models.CharField(max_length=30, unique=True, blank=True, null=True)
    last_updated_date = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['first_name'], name='idx_contact_first_name'),
            models.Index(fields=['last_name'], name='idx_contact_last_name'),
        ]

    def __str__(self):
        return f"{self.first_name + self.last_name} - {self.position if self.position else 'employed'} at {self.company if self.company else '-'}"
    
class Job(models.Model):
    JOB_STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Closed', 'Closed'),
    ]
    
    WORK_TYPE_CHOICES = [
        ('Temporary', 'Temporary'),
        ('Permanent', 'Permanent'),
    ]
    
    job_title = models.CharField(max_length=255)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, related_name="jobs", null=True)
    address = models.CharField(max_length=255)
    postcode = models.CharField(max_length=255, null=True, blank=True)
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, related_name='jobs')
    salary = models.CharField(max_length=255)
    availability = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(max_length=20, choices=JOB_STATUS_CHOICES)
    number_of_potential_candidates = models.IntegerField(default=0)
    work_type = models.CharField(max_length=20, choices=WORK_TYPE_CHOICES)
    requirements = models.JSONField(blank=True, null=True)
    geolocation = gis_models.PointField(geography=True, null=True, blank=True)
    last_updated_date = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if self.company and not self.contact:
            primary_contact = self.company.contacts.first()
            if primary_contact:
                self.contact = primary_contact
        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=['job_title'], name='idx_job_title'),
            models.Index(fields=['address'], name='idx_job_address'),
            models.Index(fields=['postcode'], name='idx_job_postcode'),
            gis_models.Index(fields=['geolocation'], name='idx_job_geolocation', condition=models.Q(geolocation__isnull=False)),
        ]

    def __str__(self):
        return f"{self.job_title} - {self.company}"
    
class Application(models.Model):
    APPLICATION_STATUS_CHOICES = [
        ('Submitted', 'Submitted'),
        ('Arranging Interview', 'Arranging Interview'),
        ('Interviewing', 'Interviewing'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
    ]
    
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='applications')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    application_status = models.CharField(max_length=20, choices=APPLICATION_STATUS_CHOICES)
    last_updated_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Application for {self.job.job_title} by {self.candidate.first_name} {self.candidate.last_name}"
    
class Placement(models.Model):
    candidate = models.ForeignKey(Candidate, on_delete=models.CASCADE, related_name='placements')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='placements')
    contact = models.ForeignKey(Contact, on_delete=models.SET_NULL, null=True, blank=True)   
    fee = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)  
    recruiter = models.CharField(max_length=255, null=True, blank=True) 
    workplace_location = models.CharField(max_length=255, null=True, blank=True)
    start_date = models.DateField(null=True, blank=True) 
    end_date = models.DateField(null=True, blank=True)
    last_updated_date = models.DateTimeField(auto_now=True)  

    def __str__(self):
        return f"{self.candidate} placed at {self.job}"