from django import forms

ROLE_CHOICES = [
    ('WNSW', 'Waking Nights Support Worker'),
    ('RSW', 'Residential Support Worker'),
    ('SRSW', 'Senior Residential Support Worker'),
    ('TL', 'Team Leader'),
    ('DM', 'Deputy Manager'),
    ('RM', 'Registered Manager'),
    ('RI', 'Responsible Individual'),
]

YES_NO_CHOICES = [
    ('yes', 'Yes'),
    ('no', 'No'),
]

QUALIFICATION_CHOICES = [
    ('L3_CYP', 'Level 3 in Children and Young People'),
    ('L3_RC', 'Level 3 in Residential Childcare'),
    ('L4_CYYF', 'Level 4 in Children, Young People and Families'),
    ('L5_LMRC', 'Level 5 in Leadership and Management (Residential Childcare)'),
    ('BSC_SW', 'BSC in Social Work'),
    ('other', 'Other'),
]

EXPERIENCE_CHOICES = [
    ('none', 'None'),
    ('up_to_6', 'Up to 6 months'),
    ('6_9', '6-9 months'),
    ('9_12', '9-12 months'),
    ('1_2', '1-2 years'),
    ('3_5', '3-5 years'),
    ('5_7', '5-7 years'),
    ('7_10', '7-10 years'),
    ('10_plus', '10+ years'),
]

COMMUTE_CHOICES = [
    ('<20', 'Less than 20 minutes'),
    ('30', 'Up to 30 minutes'),
    ('40', 'Up to 40 minutes'),
    ('50', 'Up to 50 minutes'),
    ('60', 'Up to 60 minutes'),
    ('>60', 'Over 60 minutes'),
]

DBS_CHOICES = [
    ('update', 'Yes, I have a current DBS on the update service'),
    ('not_update', 'Yes, I have a current DBS, but it is not on the update service'),
    ('none', "No, I don't have a current DBS"),
]

DRIVERS_LICENSE_CHOICES = [
    ('manual', 'Yes, Manual'),
    ('automatic', 'Yes, Automatic'),
    ('no', 'No'),
]

class CandidateForm(forms.Form):
    # 1. Multiple-choice field for interested roles
    interested_roles = forms.MultipleChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Which roles are you interested in?",
        required=True
    )
    
    # 2. UK passport or ILR
    uk_passport_or_ilr = forms.ChoiceField(
        choices=YES_NO_CHOICES,
        label="Do you have a UK passport or indefinite leave to remain?",
        required=True
    )
    
    # 3. Sponsorship requirement
    require_sponsorship = forms.ChoiceField(
        choices=YES_NO_CHOICES,
        label="Do you require sponsorship to work in the UK?",
        required=True
    )
    
    # 4. Dismissal or disciplinary proceedings
    dismissed_or_disciplinary = forms.ChoiceField(
        choices=YES_NO_CHOICES,
        label="Have you ever been dismissed from a previous role or subject to disciplinary proceedings?",
        required=True
    )
    
    # 6. Notice period
    notice_period = forms.CharField(
        label="What is your current notice period?",
        required=True
    )
    
    # 7. Qualifications (multiple answers allowed)
    qualifications = forms.MultipleChoiceField(
        choices=QUALIFICATION_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label="Do you have any of the following qualifications?",
        required=True
    )
    
    # 8. Experience in children’s residential setting
    experience_children_residential = forms.ChoiceField(
        choices=EXPERIENCE_CHOICES,
        label="How much experience do you have in a children's residential setting? (MUST be experience with children)",
        required=True
    )
    
    # 9. Area of residence
    postcode = forms.CharField(
        label="What is your postcode?",
        required=True
    )
    
    # 10. Commute time
    commute_time = forms.ChoiceField(
        choices=COMMUTE_CHOICES,
        label="How long are you willing to commute to work?",
        required=True
    )
    
    # 11. Reason for leaving current role
    reason_leaving = forms.CharField(
        label="What is the reason for leaving your current role?",
        widget=forms.Textarea,
        required=True
    )
    
    # 12. DBS status
    current_dbs = forms.ChoiceField(
        choices=DBS_CHOICES,
        label="Do you have a current DBS? If so, is your DBS on the update service?",
        required=True
    )
    
    # 13. UK driver's licence
    uk_drivers_licence = forms.ChoiceField(
        choices=DRIVERS_LICENSE_CHOICES,
        label="Do you have a UK driver's licence?",
        required=True
    )
    
    # 14. Travel method
    travelling_to_work = forms.CharField(
        label="How do you plan on travelling to work?",
        required=True
    )
    
    # 15. Current salary
    current_salary = forms.DecimalField(
        label="What's your current salary?",
        required=True,
        max_digits=10,
        decimal_places=2
    )
    
    # 16. Convictions
    convictions = forms.ChoiceField(
        choices=YES_NO_CHOICES,
        label="Do you have any spent or unspent convictions, including motor offenses?",
        required=True
    )
    
    # 17. Desired hourly rate/salary (optional)
    desired_hourly_rate = forms.DecimalField(
        label="What hourly rate/salary are you looking for?",
        required=False,
        max_digits=10,
        decimal_places=2
    )
    
    # 18. Availability for shifts (optional)
    availability_shifts = forms.CharField(
        label="What is your availability for shifts?",
        widget=forms.Textarea,
        required=False
    )
    
    # 19. Companies or sectors not wanted (optional)
    companies_excluded = forms.CharField(
        label="Are there any companies or sectors (such as LD or EBD) that you DO NOT want to work for?",
        required=False
    )
    
    # 20. CV sharing consent
    share_cv = forms.ChoiceField(
        choices=YES_NO_CHOICES,
        label=("Would you be happy for us to share your CV with potential employers for promising "
               "opportunities in your area? We’ll make sure not to send it to any companies you’ve previously "
               "mentioned as unfavoured."),
        required=True
    )
    
    # 22. Additional details (optional)
    additional_details = forms.CharField(
        label=("Any further details that would assist us with helping secure you a new role "
               "(e.g. any companies or sectors -such as LD or EBD- that you DO NOT want to work for)"),
        widget=forms.Textarea,
        required=False
    )