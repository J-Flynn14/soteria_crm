from .ai_utils import screen_cv, anonymise_cv, parse_cv, test_api_connection
from .file_utils import pdf_to_text, html_to_pdf_bytes, is_file_locked, get_file_upload_to, normalise_address_postcode
from django.core.exceptions import ObjectDoesNotExist
from django.core.files.storage import default_storage
from django.template.loader import render_to_string
from django.core.files.base import ContentFile
from django.contrib.gis.geos import Point
from django.utils.html import strip_tags
from django.core.mail import send_mail
from django.db.models import FileField
from django.core.cache import cache
from django.db import transaction
from typing import Optional, Dict, Tuple
import logging, shutil, json, os
from django.conf import settings
from celery import shared_task
from .models import Candidate
from datetime import datetime
from django.apps import apps
from io import BytesIO

logger = logging.getLogger(__name__)

# --- Refactored process_screening task ---
@shared_task()
def process_screening(candidate_id: int, cv_text: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    lock_key = None
    try:
        if cv_text is None:
            with transaction.atomic():
                candidate = Candidate.objects.select_for_update().get(id=candidate_id)
                lock_key = f"candidate_screening_lock:{candidate.first_name+candidate.last_name}"
                if not cache.add(lock_key, "locked", timeout=60):
                    logger.info(f"Screening already in progress for candidate {candidate.first_name} {candidate.last_name}. Skipping.")
                    return (None, None)
                if candidate.screening_status != "Not Screened":
                    logger.info(f"Screening already completed for candidate {candidate.first_name} {candidate.last_name}. Skipping.")
                    return (None, None)
            with candidate.cv.open('rb') as cv_file:
                pdf_text = pdf_to_text(cv_file)
                logger.info(f"🚀 Starting task: Screening")
                screening_result = screen_cv(pdf_text)
        else:
            logger.info(f"🚀 Starting task: Screening")
            screening_result = screen_cv(cv_text)

        if " | " not in screening_result:
            logger.error(f"❌ Screening result format error")
            return (None, None)
        classification, note = screening_result.split(" | ", 1)
        
        if cv_text is not None:
            logger.info(f"✅ Screened candidate successfully")
            return (classification, note)
        else:
            with transaction.atomic():
                candidate = Candidate.objects.select_for_update().get(id=candidate_id)
                update_data = {"screening_status": classification}
                filename = f"{candidate.first_name.lower()}_{candidate.last_name.lower()}_screening_notes.txt"
                candidate.screening_notes.save(filename, ContentFile(note))
                Candidate.objects.filter(pk=candidate_id).update(**update_data)
                logger.info(f"✅ Updated screening for candidate {candidate.first_name} {candidate.last_name}.")
            return (classification, note)
    except Exception as e:
        logger.error(f"❌ Error in screening candidate: {e}")
        return (None, None)
    finally:
        if cv_text is None and lock_key:
            cache.delete(lock_key)

# --- Refactored process_anonymise_cv task ---
@shared_task
def process_anonymise_cv(candidate_id: int) -> None:
    try:
        candidate = Candidate.objects.get(id=candidate_id)
        if not candidate.cv:
            logger.error(f"❌ Cv for candidate with name {candidate.first_name} {candidate.last_name} not found.")
            return None
        if candidate.anonymised_cv:
            logger.info(f"✅ Anonymised cv for candidate with name {candidate.first_name} {candidate.last_name} already present.")
            return None

        logger.info(f"🚀 Starting task: anonymise cv for candidate {candidate.first_name} {candidate.last_name}.")
        anonymised_html = anonymise_cv(pdf_to_text(candidate.cv))
        pdf_buffer = html_to_pdf_bytes(anonymised_html)
        pdf_file = ContentFile(pdf_buffer.read())
        filename = f"{candidate.first_name}_{candidate.last_name}_anonymised_cv.pdf"
        candidate._post_save_called = True
        candidate.anonymised_cv.save(filename, pdf_file)
        candidate.save()
        logger.info(f"🎯 Cv anonymisation for candidate {candidate.first_name} {candidate.last_name} completed.")
        cleanup_database.delay()
    except ObjectDoesNotExist:
        logger.error(f"❌ Candidate with ID {candidate_id} not found.")
    except Exception as e:
        logger.error(f"❌ Error processing candidate cv {candidate.first_name} {candidate.last_name}: {str(e)}")
    return None

# --- Refactored cleanup_database task ---
@shared_task
def cleanup_database() -> str:
    lock_id = "cleanup_database_lock"
    if cache.get(lock_id):
        logger.warning("⚠️ Cleanup task is already running. Skipping execution.")
        return "skipped"
    cache.set(lock_id, True, timeout=2)
    try:
        logger.info("🚀 Starting Task: cleanup_database")
        all_models = list(apps.get_models())
        referenced_files = set()
        media_root = settings.MEDIA_ROOT
        orphaned_folder = os.path.join(media_root, "orphaned_files")
        os.makedirs(orphaned_folder, exist_ok=True)

        for model in all_models:
            file_fields = [field for field in model._meta.fields if isinstance(field, FileField)]
            if not file_fields:
                continue
            logger.info(f"📂 Checking model: {model.__name__}")
            qs = model.objects.all().iterator()
            for instance in qs:
                update_data = {}
                for field in file_fields:
                    file_instance = getattr(instance, field.name)
                    if file_instance and file_instance.name:
                        relative_path = file_instance.name.replace("\\", "/")
                        if not default_storage.exists(relative_path):
                            logger.warning(f"⚠️ File not found: {relative_path}. Removing reference from {field.name} in {model.__name__}.")
                            update_data[field.name] = None
                        else:
                            referenced_files.add(relative_path)
                if update_data:
                    model.objects.filter(pk=instance.pk).update(**update_data)
                    logger.info(f"✅ Updated {model.__name__} ID {instance.id}: Removed missing file references.")

        logger.info("🔍 Checking for orphaned files in MEDIA_ROOT.")
        for root, _, files in os.walk(media_root):
            for file in files:
                full_path = os.path.join(root, file)
                file_relative_path = os.path.relpath(full_path, media_root).replace("\\", "/")
                if file_relative_path.startswith("orphaned_files/"):
                    continue
                if file_relative_path not in referenced_files:
                    backup_full_path = os.path.join(orphaned_folder, file_relative_path)
                    backup_dir = os.path.dirname(backup_full_path)
                    os.makedirs(backup_dir, exist_ok=True)
                    try:
                        if os.path.exists(full_path) and not is_file_locked(full_path):
                            shutil.move(full_path, backup_full_path)
                            logger.warning(f"📦 Moved orphaned file to backup: {backup_full_path}")
                        else:
                            logger.warning(f"🔒 Skipping locked file: {full_path}")
                    except Exception as e:
                        logger.error(f"❌ Error moving file {full_path} to {backup_full_path}: {e}")
                        continue
        logger.info("🔍 Checking for empty folders in MEDIA_ROOT.")
        for root, dirs, _ in os.walk(media_root, topdown=False):
            rel_root = os.path.relpath(root, media_root).replace("\\", "/")
            if rel_root == "." or rel_root.startswith("orphaned_files"):
                continue
            if not os.listdir(root):
                try:
                    os.rmdir(root)
                    logger.info(f"🗑️ Deleted empty folder: {root}")
                except Exception as e:
                    logger.error(f"❌ Error deleting folder {root}: {e}")
                    continue
        logger.info("🎯 Full file cleanup process completed.")
    finally:
        cache.delete(lock_id)
    return "done"

# --- Refactored delete_orphaned_files task ---
@shared_task
def delete_orphaned_files() -> str:
    logger.info("🚀 Starting Task: delete_orphaned_files")
    orphaned_folder = os.path.join(settings.MEDIA_ROOT, "orphaned_files")
    if not os.path.exists(orphaned_folder):
        logger.info("✅ Orphaned files folder does not exist. Nothing to delete.")
        return "nothing to delete"
    files_deleted = 0
    for root, dirs, files in os.walk(orphaned_folder, topdown=False):
        for file in files:
            file_path = os.path.join(root, file)
            try:
                os.remove(file_path)
                files_deleted += 1
                logger.info(f"🗑️ Deleted orphaned file: {file_path}")
            except Exception as e:
                logger.error(f"❌ Error deleting file {file_path}: {e}")
                continue
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            try:
                if not os.listdir(dir_path):
                    os.rmdir(dir_path)
                    logger.info(f"🗑️ Removed empty directory: {dir_path}")
            except Exception as e:
                logger.error(f"❌ Error removing directory {dir_path}: {e}")
                continue
    logger.info(f"🎯 Orphaned files cleanup complete. {files_deleted} files deleted.")
    return "done"

# --- Refactored send_screening_form task ---
@shared_task
def send_screening_form(candidate_id: int) -> None:
    try:
        candidate = Candidate.objects.get(id=candidate_id)
        if candidate.form_submission_status == "Submitted":
            logger.info(f"✅ Screening form already submitted by candidate {candidate.first_name} {candidate.last_name}. Skipping.")
            return None
        context = {"candidate_name": candidate.first_name, "default_email": settings.DEFAULT_FROM_EMAIL}
        send_mail(
            subject="Express Your Interest in Residential Childcare Opportunities",
            message=strip_tags('email_template.html'),
            html_message=render_to_string('email_template.html', context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[candidate.email],
            fail_silently=False,
        )
        candidate.form_submission_status = "Pending"
        candidate.screening_first_sent = datetime.now()
        candidate.save(update_fields=["form_submission_status", "screening_first_sent"])
        logger.info(f"📨 Screening form sent to candidate {candidate.first_name} {candidate.last_name}")
    except Candidate.DoesNotExist:
        logger.error(f"❌ Candidate {candidate_id} not found.")
        return None
    except Exception as e:
        logger.error(f"❌ Error sending screening form to Candidate {candidate.first_name} {candidate.last_name}: {e}")
        return None
    return None

# --- Refactored process_candidate_from_cv task ---
@shared_task
def process_candidate_from_cv(cv_file_path: str) -> None:
    try:
        with open(cv_file_path, 'rb') as f:
            cv_file_content = f.read()
    except Exception as e:
        logger.error(f"❌ Error opening file at {cv_file_path}: {e}")
        return None

    # Helper: Remove markdown code fences.
    def clean_output(raw_output: str) -> str:
        cleaned = raw_output.strip()
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip().startswith("```"):
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()
        return cleaned

    # Helper: Clean string values.
    def clean_str(value) -> Optional[str]:
        if isinstance(value, str):
            val = value.strip()
            return val if val else None
        elif isinstance(value, list):
            joined = ", ".join(str(item).strip() for item in value if str(item).strip())
            return joined if joined else None
        return value

    # Helper: Convert numeric value to float or None.
    def clean_decimal(value) -> Optional[float]:
        if not value or str(value).strip() == "":
            return None
        try:
            return float(value)
        except ValueError:
            return None

    logger.info(f"🚀 Starting Task: process_candidate_from_cv")
    file_obj = BytesIO(cv_file_content)
    cv_text = pdf_to_text(file_obj)
    # Call parse_cv synchronously (do not use .delay())
    raw_output = parse_cv(cv_text)
    cleaned = clean_output(raw_output)
    try:
        fields = json.loads(cleaned)
    except Exception as e:
        logger.error(f"Error parsing AI output: {e}")
        fields = {}
        return None

    first_name = clean_str(fields.get("first name", ""))
    last_name = clean_str(fields.get("last name", ""))
    if not first_name or not last_name:
        logger.warning("⚠️ Candidate creation aborted: first name or last name is missing.")
        return None

    mobile_num = clean_str(fields.get("mobile number", ""))
    email = clean_str(fields.get("email", ""))
    current_salary = clean_decimal(fields.get("current_salary", ""))
    desired_hourly_rate = clean_decimal(fields.get("desired_hourly_rate", ""))

    candidate_data = {
        "first_name": first_name,
        "last_name": last_name,
        "mobile_num": mobile_num,
        "email": email,
        "address": clean_str(fields.get("address", "")),
        "postcode": clean_str(fields.get("postcode", "")),
        "position": clean_str(fields.get("position", "")),
        "employer": clean_str(fields.get("employer", "")),
        "roles_interested": fields.get("roles_interested", []),
        "uk_drivers_licence": clean_str(fields.get("uk_drivers_licence", "")),
        "notice_period": clean_str(fields.get("notice_period", "")),
        "qualifications": fields.get("qualifications", []),
        "experience": fields.get("experience", []),
        "commute_time": clean_str(fields.get("commute_time", "")),
        "current_dbs": clean_str(fields.get("current_dbs", "")),
        "current_salary": current_salary,
        "convictions": fields.get("convictions", False),
        "desired_hourly_rate": desired_hourly_rate,
        "availability_shifts": clean_str(fields.get("availability_shifts", "")),
    }
    
    candidate_data = {k: v for k, v in candidate_data.items() if v is not None}
    required_keys = ["first_name", "last_name", "email", "address"]
    missing = [key for key in required_keys if not candidate_data.get(key)]
    if missing:
        logger.warning(f"⚠️ Candidate creation aborted: missing required fields: {missing}")
        return None

    existing_candidate = None
    if mobile_num:
        existing_candidate = Candidate.objects.filter(mobile_num=mobile_num).first()
    if not existing_candidate and email:
        existing_candidate = Candidate.objects.filter(email=email).first()
    if existing_candidate:
        logger.warning(f"⚠️ Candidate with mobile {mobile_num} or email {email} already exists.")
        return None
    
    try:
        with transaction.atomic():
            candidate = Candidate.objects.create(**candidate_data)
            original_filename = os.path.basename(cv_file_path)
            relative_path = get_file_upload_to(candidate, original_filename)
            dest_absolute_path = os.path.join(settings.MEDIA_ROOT, relative_path)
            dest_folder = os.path.dirname(dest_absolute_path)
            os.makedirs(dest_folder, exist_ok=True)
            shutil.move(cv_file_path, dest_absolute_path)
            candidate.cv.name = relative_path

            # Schedule screening asynchronously (do not wait for its result)
            try: 
                status, note = process_screening.run(candidate_id=candidate.id, cv_text=cv_text)
                candidate.screening_status = status
                filename = f"{candidate.first_name.lower()}_{candidate.last_name.lower()}_screening_notes.txt"
                candidate.screening_notes = ContentFile(note, name=filename)
            except Exception as e: pass
            try:
                geocode_result = process_geocode_address.run(candidate.address, candidate.postcode)
                point = Point(geocode_result["longitude"], geocode_result["latitude"], srid=4326)
                candidate.geolocation = point
            except Exception as e: pass

            candidate.save()
    except Exception as e:
        logger.error(f"❌ Error creating candidate: {e}")
        return None

    logger.info(f"🎯 Candidate {candidate.first_name} {candidate.last_name} created successfully from CV.")
    return None

@shared_task
def process_test_api_connection() -> str:
    output = test_api_connection()
    if output == 'Hello World!':
        return "API connection successful."
    else:
        return output

@shared_task(bind=True, max_retries=3)
def process_geocode_address(self, address: str, postcode: str, timeout: int = 10) -> Optional[Dict[str, float]]:
    logger.info(f"🚀 Starting Task: process_geocode_address for {address}")
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut

    normalized_address, normalized_postcode = normalise_address_postcode(address, postcode)
    full_address = f"{normalized_address} {normalized_postcode}" if normalized_postcode else normalized_address

    geolocator = Nominatim(user_agent="uk_geocoder")
    try:
        location = geolocator.geocode(full_address, country_codes="gb", addressdetails=True, timeout=timeout)
    except GeocoderTimedOut as exc:
        logger.warning(f"⚠️ Geocoding timed out for address: {address}. Retrying...")
        raise self.retry(exc=exc, countdown=5)
    
    if not location:
        logger.warning(f"⚠️ Geocoding failed for address: {address}")
        return None

    logger.info(f"✅ Geogoding successful for address: {address}")
    return {"latitude": location.latitude, "longitude": location.longitude}

@shared_task
def update_geolocation_from_address(address: str, postcode: str, timeout: int = 10) -> None:
    from crm.tasks import process_geocode_address  # Import here to avoid circular dependencies
    
    geocode_result = process_geocode_address(address, postcode, timeout=timeout)
    if not geocode_result:
        return None
    else:
        models_to_update = [
            apps.get_model('crm', 'Candidate'),
            apps.get_model('crm', 'Job')
        ]
        for model in models_to_update:
            try:
                with transaction.atomic():
                    normalized_address, normalized_postcode = normalise_address_postcode(address, postcode)
                    filters = {'address__iexact': normalized_address, 'geolocation__isnull': True}
                    if postcode:
                        filters['postcode__iexact'] = normalized_postcode
                    updated = model.objects.filter(**filters).update(geolocation=Point(geocode_result["longitude"], geocode_result["latitude"], srid=4326))
                    if updated:
                        logger.info(f"✅ Updated geolocation for {updated} {model.__name__} instance(s) with address '{normalized_address}' and postcode '{normalized_postcode}'")
            except Exception as e:
                logger.error(f"Error updating geolocation for model {model.__name__} with address '{normalized_address}' and postcode '{normalized_postcode}': {e}")
                continue
        return None

