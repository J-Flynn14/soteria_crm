from django.template.loader import render_to_string
from .file_utils import extract_body_html
from django.conf import settings
from openai import OpenAI
from collections import Counter
import logging
logger = logging.getLogger(__name__)

def get_openai_client() -> OpenAI:
    return OpenAI(
    api_key=f'{settings.OPENAI_API_KEY}',
    organization=f'{settings.OPENAI_ORGANIZATION}',
    project=f'{settings.OPENAI_PROJECT}')

def test_api_connection() -> str:
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "system", "content": "output the text inside the quotes: 'Hello World!'"}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"{e}"

def parse_cv(cv_text: str) -> str:
    prompt = """
    Extract all the following information from the CV text given.
    Return your answer as a valid JSON object with exactly these keys:
    - first name (e.g. John),
    - last name (e.g. Smith),
    - mobile number (as a string),
    - email (as a string),
    - address (excluding postcode as a string),
    - postcode (as a string),
    - position (most recent job position),
    - employer (most recent employer),
    - roles_interested (any job roles mentioned as an array of strings, or an empty array),
    - uk_drivers_licence (if mentioned, e.g. "manual" or "automatic", else an empty string),
    - notice_period (text, or an empty string),
    - qualifications (an array of qualification strings, e.g. ("Level 2 Diploma in Health and Social Care"),
    - experience (skill - years/months for each skill mentioned as an array of strings, or an empty array),
    - commute_time (maximum commute time if mentioned, or an empty string),
    - current_dbs (if mentioned, use this format: ('update', 'Yes, I have a current DBS on the update service'), ('not_update', 'Yes, I have a current DBS, but it is not on the update service'), else an empty string),
    - current_salary (most recent salary mentioned as a number, or an empty string),
    - convictions (true or false),
    - desired_hourly_rate (a number if mentioned, or an empty string),
    - availability_shifts (availability if mentioned e.g. Mon-Fri, or an empty string),

    If any information is not mentioned in the CV, return an empty string (or false/empty array as appropriate).
    If a qualification is ambiguous e.g. "Level 3 in Health and Social Care", assume it is a "Level 3 Diploma in Health and Social Care", also make sure that dipolmas are not mistaken for degrees, GSCE's or A-levels (they will have Level X before)
    """

    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an AI assistant trained to extract structured data from CVs. Always return output in valid JSON format."},
                {"role": "user", "content": f"{prompt}\n\nCV Text:\n{cv_text}"}
            ],
            temperature=0.2,
            max_tokens=500
        )
        if response and response.choices and response.choices[0].message:
            return response.choices[0].message.content.strip()
        else:
            return "No content in response."

    except Exception as e:
        return f"Error in parsing CV: {e}"

def screen_cv(cv_text:str) -> str:
    prompt = """
Your task is to analyse a candidate's CV provided as text and determine their qualification status for a role. You must always output a string in the exact format: "status | note", where neither the status nor the note is blank. 

Guidelines:
1. If the candidate qualifies for one or more roles, always choose the highest paying role.
2. If it cannot be determined whether the candidate is qualified for any role, default to "Intermediate".
3. If the candidate has already worked in one of the roles (or a similar role) in the past, classify them as "Qualified - [Role]" for that role.
4. If the candidate has the required experience and their qualifications (even if only desirable) match a role, classify them as "Qualified - [Role]".
5. If the candidate has experience in residential support work but the CV does not specify childcare, classify them as "Intermediate".
6. Examine the CV for any work experience within the last 5 years that is outside of these locations: England, Scotland, Wales, Northern Ireland, Ireland, America, or any European country. (Note: Sometimes a foreign city or workplace is named instead of the country. If no location is mentioned for a job, assume it was in the UK.) If such experience is found, classify the candidate as "Unqualified - Out of country".
7. Scan the CV for profanity or unprofessional language. If detected, classify the candidate as "Unqualified - NSFW".

Always output your result exactly as: "status | note", with a clear status and a brief explanation in the note. Do not leave either field blank.
 
Roles: 
1.) Qualified - RM
2.) Qualified - DM
3.) Qualified - TL
4.) Qualified - SRSW
5.) Qualified - RSW
6.) Intermediate
7.) Unqualified
8.) Unqualified - Out of country
9.) Unqualified - NSFW

Standard Qualifications:
Level 3 in Children and Young People’s Workforce OR
Level 3 in Residential Childcare OR
Level 4 in Children, Young People, and Families OR
Level 4 Young People and Families Practitioner

Registered Manager (RM)
Experience:
2+ years in a position relevant to residential childcare within the last 5 years.
1+ year supervising and managing staff in a care role.
Must have been an Ofsted Registered Manager (not CQC).
Qualifications:
Level 5 Leadership and Management for Residential Childcare OR
Level 5 Diploma in Leadership for Health & Social Care and Children & Young People’s Services OR
Degree in Social Work.

Deputy Manager (DM)
Experience:
12+ months in a supervisory residential childcare role (e.g., Senior Support Worker, Team Leader).
2+ years of experience in residential childcare.
Qualifications:
Standard Qualifications

Team Leader (TL)
Experience:
2+ years in a residential children’s home.
1+ year as a Senior Residential Support Worker (SRSW).
Qualifications:
Standard Qualifications

Senior Residential Support Worker (SRSW)
Experience:
1+ year in a residential children’s home.
Qualifications (Desirable but not required):
Standard Qualifications

Residential Support Worker (RSW)
Experience:
Minimum 3-6 months in a residential childcare role.
Alternative backgrounds considered (foster care, working with 16+).
Qualifications (Desirable but not required):
Standard Qualifications
"""
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"CV Text:\n{cv_text}"}
            ],
            temperature=0.2,
            max_tokens=500,
        )
        logger.info(f"raw screening output: {response.choices[0].message.content.strip()}")
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        return f"Error in screening CV: {e}"

def anonymise_cv(cv_text:str) -> str:
    prompt = """
Task: Format and anonymize the provided CV for use in a children’s home hiring process.

Context:

This is Step 1 of a four-step process. The goal is to anonymize and professionally format the candidate’s CV into the specified HTML layout using the Soteria People branding and style. To optimize token usage and focus on relevance, include only roles directly related to children’s care, safeguarding, or residential care settings. The formatted CV will serve as the foundation for compliance checks and recruiter review.

Inputs:
	1.	Raw CV Data (text).

Instructions:
	1.	Role Selection:
	•	Review all work experience entries and include only roles that meet one or more of the following criteria:
	•	Involve direct or indirect work with children or young people (e.g., residential care, education, safeguarding).
	•	Relate to caregiving, healthcare, or social work with minors.
	•	Include transferable skills relevant to children’s care settings (e.g., crisis management, mentoring, or support work).
	•	Exclude roles unrelated to children’s care unless explicitly requested by the user.
	2.	Anonymization Process:
	•	Remove all personal and identifiable information:
	•	Candidate names, contact details, and specific workplace names.
	•	Replace workplace names with generic terms like “Healthcare Organization” or “Residential Care Facility.”
	•	Truncate postcodes to the first three characters (e.g., “SW11 5DW” → “SW1”).
	•	Ensure consistent anonymization throughout.
	3.	Formatting Process:
	•	Use the Soteria People CV template for styling and layout:
	•	Include a Qualifications section at the top.
	•	List Work Experience in reverse chronological order, limiting entries to relevant roles.
	•	Clearly indicate if roles were in children’s or adults’ residential care.
	•	Ensure the structure aligns with the provided design:
	•	Use <h2> for section headers, <h3> for job titles, and <ul> with <li> tags for responsibilities.
	4.	Validation:
	•	Ensure:
	•	Only relevant roles are included, with non-relevant entries omitted.
	•	All included work experience is in reverse chronological order.
	•	Anonymization has been applied consistently and comprehensively.

Expected Output:
I want all quotations removed, the only output should be the html code.
	1.	A fully anonymized, formatted CV in the Soteria People HTML layout:
	•	Styled with Soteria People branding, professional fonts, and clean design.
	•	Headings (<h2> and <h3>) styled with the accent color #0051a3.
	•	Footer with contact details for Soteria People.

<body>
    <div class="cv-container">
        <!-- Black Header -->
        <div class="header-black">
            <img src="https://soteriapeople.co.uk/wp-content/uploads/2024/12/cropped-SoteriaPeople2.png" alt="Soteria People Logo">
            <div class="header-text">
                Soteria People - Protect - Envelop - Nurture
            </div>
        </div>
        <!-- Blue Section -->
        <div class="header-blue"></div>
        <div class="content">
            <!-- Candidate's Name and Title -->
            <h2>[Candidate’s Job Title]</h2>
            <p>[Brief professional summary highlighting experience and expertise]</p>

            <!-- Qualifications Section -->
            <h2>Qualifications</h2>
            <ul>
                <li>[Degree, University, Year]</li>
                <li>[Certifications or Training]</li>
            </ul>

            <!-- Work Experience Section -->
            <h2>Work Experience</h2>
            <div class="section">
                <h3>[Role Title] - [Organization]</h3>
                <p>[Dates]</p>
                <ul>
                    <li>[Responsibility 1]</li>
                    <li>[Responsibility 2]</li>
                </ul>
                <!-- Repeat for additional roles -->
            </div>

            <!-- Skills Section -->
            <h2>Skills</h2>
            <ul>
                <li>[Skill 1]</li>
                <li>[Skill 2]</li>
            </ul>
        </div>
        <!-- Footer -->
        <div class="footer">
            <p>20 Wenlock Road, London, N1 7GU</p>
            <p>+44 1925 973319 | <a href="mailto:info@soteriapeople.co.uk">info@soteriapeople.co.uk</a></p>
            <p>© 2024 Soteria People</p>
        </div>
    </div>
</body>

"""
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an AI assistant trained to format and anonymize a CV. Always return output in valid HTML format"},
                {"role": "user", "content": f"{prompt}\n\nCV Text:\n{cv_text}"}
            ],
            temperature=0.2,
            max_tokens=500
        )
        if response and response.choices and response.choices[0].message:
            return render_to_string('anon_cv_styles.html') + extract_body_html(response.choices[0].message.content.strip())
        else:
            return "No content in response."

    except Exception as e:
        return f"Error in anonymizing CV: {e}"
