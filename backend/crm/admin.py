from django.utils.html import format_html
from django.contrib import messages, admin
from django.urls import reverse
from .models import (
    Candidate, 
    Contact, 
    Job, 
    Application, 
    Placement, 
    Company)
from .tasks import (
    process_screening,
    process_anonymise_cv,
    cleanup_database,
    delete_orphaned_files,
    send_screening_form)

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = (
        'first_name', 'last_name', 'email', 'mobile_num', 'address', 'get_position', 'get_employer', 'cv', 'screening_status',
        'form_submission_status',
    )
    list_filter = ('screening_status', 'form_submission_status')
    search_fields = ('first_name', 'last_name', 'email', 'address')

    def get_position(self, obj):
        return obj.position
    get_position.short_description = "Current Job Title"

    def get_employer(self, obj):
        return obj.employer
    get_employer.short_description = "Current Employer"

    def trigger_screening(self, request, queryset):
        for candidate in queryset:
            process_screening.delay(candidate.id, None)  
        self.message_user(request, "🚀 Screening has been triggered for selected candidates.", level=messages.SUCCESS)
    trigger_screening.short_description = "🔎 Screen CV"

    def trigger_send_screening_form(self, request, queryset):
        for candidate in queryset:
            send_screening_form.delay(candidate.id) 
        self.message_user(request, "🚀 Send screening form has been triggered.", level=messages.SUCCESS)
    trigger_send_screening_form.short_description = "🚀 Send Screening Form"

    def trigger_anonymise_cv(self, request, queryset):
        for candidate in queryset:
            process_anonymise_cv.delay(candidate.id) 
        self.message_user(request, "🚀 CV Anonymisation has been triggered for selected candidates.", level=messages.SUCCESS)
    trigger_anonymise_cv.short_description = "🔒 Anonymise CV"

    def trigger_cleanup_database(self, request, queryset):
        cleanup_database.delay() 
        self.message_user(request, "🚀 Database Cleanup has been triggered.", level=messages.SUCCESS)
    trigger_cleanup_database.short_description = "🗑️ Cleanup Database"

    def trigger_delete_orphaned_files(self, request, queryset):
        delete_orphaned_files.delay() 
        self.message_user(request, "🚀 Orphaned Files Cleanup has been triggered.", level=messages.SUCCESS)
    trigger_delete_orphaned_files.short_description = "🗑️ Delete Orphaned Files"

    actions = [
        trigger_screening,
        trigger_send_screening_form,
        trigger_anonymise_cv,
        trigger_cleanup_database,
        trigger_delete_orphaned_files,
    ]

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = (
        'first_name', 'last_name', 'email', 'mobile_num', 'get_position', 'company', 
    )
    search_fields = ('first_name', 'last_name', 'email')

    def get_position(self, obj):
        return obj.position
    get_position.short_description = "Current Job Title"

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'industry', 
    )
    search_fields = ('name', 'industry')

    def get_position(self, obj):
        return obj.position
    get_position.short_description = "Current Job Title"

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        'job_title', 'company', 'get_contact', 'status', 'work_type', 'number_of_potential_candidates',
    )
    list_filter = ('status', 'work_type')
    search_fields = ('job_title', 'company', 'status', 'work_type')
    
    def get_contact(self, obj):
        if obj.contact:
            url = reverse("admin:crm_contact_change", args=[obj.contact.id])
            return format_html('<a href="{}">{}</a>', url, obj.contact)
        return "-"
    get_contact.short_description = "Contact"

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        'candidate', 'get_job', 'application_status', 'last_updated_date',
    )
    list_filter = ('application_status',)
    search_fields = ('candidate', 'job', 'application_status')

    def get_job(self, obj):
        if obj.job:
            url = reverse("admin:crm_job_change", args=[obj.job.id])
            return format_html('<a href="{}">{}</a>', url, obj.job)
        return "-"
    get_job.short_description = "Job"
    
@admin.register(Placement)
class PlacementAdmin(admin.ModelAdmin):
    list_display = (
        'candidate', 'get_job', 'get_contact', 'fee', 'recruiter',
        'workplace_location', 'start_date', 'end_date'
    )
    search_fields = ('candidate', 'job')

    def get_position(self, obj):
        return obj.position
    get_position.short_description = "Job Title"

    def get_job(self, obj):
        if obj.job:
            url = reverse("admin:crm_job_change", args=[obj.job.id])
            return format_html('<a href="{}">{}</a>', url, obj.job)
        return "-"
    get_job.short_description = "Job"

    def get_contact(self, obj):
        if obj.job:
            url = reverse("admin:crm_contact_change", args=[obj.contact.id])
            return format_html('<a href="{}">{}</a>', url, obj.contact)
        return "-"
    get_job.short_description = "Contact"


