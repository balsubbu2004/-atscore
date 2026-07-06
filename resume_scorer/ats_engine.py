import re
import os
import json
import pdfplumber
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from groq import Groq

USE_NLP = os.getenv('USE_NLP', 'False') == 'True'

if USE_NLP:
    from sentence_transformers import SentenceTransformer, util
    _model = None

    def get_model():
        global _model
        if _model is None:
            _model = SentenceTransformer('all-MiniLM-L6-v2')
        return _model

# ── Constants ────────────────────────────────────────────
SECTION_PATTERNS = {
    'summary': r'(professional\s+summary|summary|objective|profile|about\s+me)',
    'skills': r'(technical\s+skills|skills|technologies|competencies|expertise)',
    'experience': r'(experience|work\s+experience|employment|internship|career)',
    'projects': r'(projects|personal\s+projects|academic\s+projects|portfolio)',
    'education': r'(education|academic|qualifications|degrees)',
    'certifications': r'(certifications?|certificates?|courses?|training)',
}

SECTION_WEIGHTS = {
    'skills': 0.40,
    'experience': 0.15,
    'projects': 0.30,
    'summary': 0.10,
    'education': 0.03,
    'certifications': 0.02,
}

ACTION_VERBS = [
    'built', 'developed', 'implemented', 'designed', 'created', 'led',
    'managed', 'optimized', 'improved', 'reduced', 'increased', 'delivered',
    'architected', 'deployed', 'integrated', 'automated', 'debugged', 'fixed',
    'collaborated', 'contributed', 'analyzed', 'identified', 'resolved',
    'established', 'launched', 'migrated', 'refactored', 'tested', 'documented',
    'trained', 'mentored', 'coordinated', 'streamlined', 'maintained'
]


# ── PDF Extraction ───────────────────────────────────────
def extract_text_from_pdf(pdf_path):
    text = ""
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()


# ── Section Parser ───────────────────────────────────────
def parse_sections(text):
    lines = text.split('\n')
    sections = {key: [] for key in SECTION_PATTERNS}
    sections['other'] = []
    current_section = 'other'

    for line in lines:
        line_lower = line.lower().strip()
        matched = False
        for section, pattern in SECTION_PATTERNS.items():
            if re.search(pattern, line_lower) and len(line.strip()) < 60:
                current_section = section
                matched = True
                break
        if not matched:
            sections[current_section].append(line)

    return {k: '\n'.join(v).strip() for k, v in sections.items()}


# ── Keyword Extraction ───────────────────────────────────
def extract_keywords(text, max_features=50):
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s\+\#]', ' ', text)

    stop_words = [
        'the', 'and', 'for', 'with', 'you', 'are', 'our',
        'will', 'have', 'this', 'that', 'from', 'your',
        'we', 'be', 'to', 'of', 'in', 'a', 'is', 'it',
        'an', 'as', 'at', 'by', 'or', 'on', 'do', 'if',
        'was', 'has', 'had', 'but', 'not', 'they', 'their'
    ]

    try:
        vectorizer = TfidfVectorizer(
            stop_words=stop_words,
            ngram_range=(1, 1),
            max_features=max_features
        )
        vectorizer.fit([text])
        return vectorizer.get_feature_names_out().tolist()
    except Exception:
        return []


# ── TF-IDF Similarity ────────────────────────────────────
def tfidf_similarity(text1, text2):
    if not text1.strip() or not text2.strip():
        return 0.0
    try:
        vectorizer = TfidfVectorizer()
        tfidf_matrix = vectorizer.fit_transform([text1, text2])
        score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
        return round(float(score), 4)
    except Exception:
        return 0.0


# ── Semantic Similarity ──────────────────────────────────
def semantic_similarity(text1, text2):
    if USE_NLP:
        if not text1.strip() or not text2.strip():
            return 0.0
        model = get_model()
        emb1 = model.encode(text1, convert_to_tensor=True)
        emb2 = model.encode(text2, convert_to_tensor=True)
        score = util.cos_sim(emb1, emb2).item()
        return round(max(0.0, min(1.0, score)), 4)
    else:
        return tfidf_similarity(text1, text2)


# ── Groq AI JD Matcher ───────────────────────────────────
def groq_jd_match(resume_text, job_description):
    api_key = os.getenv('GROQ_API_KEY')

    if not api_key:
        print("Groq error: GROQ_API_KEY not found in environment")
        return None, [], [], {}, []

    try:
        client = Groq(api_key=api_key)

        prompt = f"""You are an expert ATS (Applicant Tracking System) analyzer.

Analyze this resume against the job description and return a JSON response only.

RESUME:
{resume_text[:3000]}

JOB DESCRIPTION:
{job_description[:1500]}

Return ONLY this JSON with no explanation, no markdown, no code blocks:
{{
    "jd_match_score": <integer 0-100 representing how well resume matches the JD>,
    "matched_skills": [<list of skills from JD found in resume, max 15 items>],
    "missing_skills": [<list of important skills from JD missing in resume, max 10 items>],
    "section_scores": {{
        "skills": <integer 0-100>,
        "experience": <integer 0-100>,
        "projects": <integer 0-100>,
        "summary": <integer 0-100>,
        "education": <integer 0-100>,
        "certifications": <integer 0-100>
    }},
    "suggestions": [<list of 3-5 specific actionable improvement suggestions as strings>]
}}"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
        )

        raw = response.choices[0].message.content.strip()
        # Clean markdown if present
        raw = re.sub(r'```json|```', '', raw).strip()

        data = json.loads(raw)

        return (
            data.get('jd_match_score', 0),
            data.get('matched_skills', []),
            data.get('missing_skills', []),
            data.get('section_scores', {}),
            data.get('suggestions', [])
        )

    except json.JSONDecodeError as e:
        print(f"Groq JSON parse error: {e}")
        print(f"Raw response was: {raw}")
        return None, [], [], {}, []
    except Exception as e:
        print(f"Groq error: {type(e).__name__}: {e}")
        return None, [], [], {}, []


# ── Resume Quality Scorer ────────────────────────────────
def score_resume_quality(resume_text, sections):
    quality_breakdown = {}
    resume_lower = resume_text.lower()
    word_count = len(resume_text.split())

    # 1. Section completeness (20 points)
    key_sections = ['summary', 'skills', 'experience', 'projects', 'education']
    found_sections = sum(1 for s in key_sections if sections.get(s, '').strip())
    section_score = round((found_sections / len(key_sections)) * 20)
    quality_breakdown['sections'] = {
        'score': section_score,
        'max': 20,
        'detail': f'{found_sections}/{len(key_sections)} key sections found'
    }

    # 2. Action verbs (15 points)
    exp_text = sections.get('experience', '') + ' ' + sections.get('projects', '')
    exp_lower = exp_text.lower()
    found_verbs = [v for v in ACTION_VERBS if v in exp_lower]
    verb_score = min(15, round((len(found_verbs) / 8) * 15))
    quality_breakdown['action_verbs'] = {
        'score': verb_score,
        'max': 15,
        'detail': f'{len(found_verbs)} action verbs found'
    }

    # 3. Quantified achievements (15 points)
    number_pattern = r'\b\d+[\+\%]?\s*(users?|students?|bugs?|issues?|processes?|languages?|months?|years?|hours?|minutes?|mb|gb|ms|k|million)?\b'
    numbers_found = re.findall(number_pattern, resume_lower)
    quant_score = min(15, len(numbers_found) * 3)
    quality_breakdown['quantification'] = {
        'score': quant_score,
        'max': 15,
        'detail': f'{len(numbers_found)} quantified achievements found'
    }

    # 4. Contact info (10 points)
    has_email = bool(re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', resume_text))
    has_phone = bool(re.search(r'[\+]?[\d\s\-\(\)]{8,}', resume_text))
    has_linkedin = 'linkedin' in resume_lower
    has_github = 'github' in resume_lower
    contact_count = sum([has_email, has_phone, has_linkedin, has_github])
    contact_score = round((contact_count / 4) * 10)
    quality_breakdown['contact_info'] = {
        'score': contact_score,
        'max': 10,
        'detail': f'{contact_count}/4 contact fields present'
    }

    # 5. Summary quality (10 points)
    summary_text = sections.get('summary', '')
    summary_words = len(summary_text.split())
    if summary_words >= 50:
        summary_score = 10
    elif summary_words >= 30:
        summary_score = 7
    elif summary_words >= 10:
        summary_score = 4
    else:
        summary_score = 0
    quality_breakdown['summary_quality'] = {
        'score': summary_score,
        'max': 10,
        'detail': f'Summary has {summary_words} words'
    }

    # 6. Skills section (10 points)
    skills_text = sections.get('skills', '')
    skills_count = len([s for s in re.split(r'[,\n|]', skills_text) if s.strip()])
    skills_score = min(10, round((skills_count / 10) * 10))
    quality_breakdown['skills_depth'] = {
        'score': skills_score,
        'max': 10,
        'detail': f'{skills_count} skills listed'
    }

    # 7. Projects with tech stack (10 points)
    projects_text = sections.get('projects', '')
    tech_keywords = ['python', 'django', 'flask', 'react', 'javascript', 'postgresql',
                     'sql', 'api', 'git', 'docker', 'linux', 'node', 'mongodb',
                     'sqlite', 'tensorflow', 'pytorch', 'aws', 'firebase']
    techs_in_projects = [t for t in tech_keywords if t in projects_text.lower()]
    projects_score = min(10, len(techs_in_projects) * 2)
    quality_breakdown['projects_tech'] = {
        'score': projects_score,
        'max': 10,
        'detail': f'{len(techs_in_projects)} technologies mentioned in projects'
    }

    # 8. Resume length (10 points)
    if 300 <= word_count <= 700:
        length_score = 10
    elif 200 <= word_count <= 900:
        length_score = 7
    elif word_count < 200:
        length_score = 3
    else:
        length_score = 5
    quality_breakdown['resume_length'] = {
        'score': length_score,
        'max': 10,
        'detail': f'{word_count} words total'
    }

    total_quality = sum(v['score'] for v in quality_breakdown.values())
    return total_quality, quality_breakdown


# ── JD Match Scorer (TF-IDF fallback) ───────────────────
def score_jd_match(resume_text, job_description, sections):
    jd_keywords = extract_keywords(job_description, max_features=40)

    section_scores = {}
    for section in SECTION_WEIGHTS:
        section_text = sections.get(section, '')
        if not section_text.strip():
            section_scores[section] = 0
            continue

        section_lower = section_text.lower()
        matched = [kw for kw in jd_keywords if kw in section_lower]
        keyword_score = (len(matched) / len(jd_keywords) * 100) if jd_keywords else 0
        sem_score = semantic_similarity(section_text, job_description) * 100
        section_scores[section] = round((keyword_score * 0.5) + (sem_score * 0.5))

    overall_semantic = semantic_similarity(resume_text, job_description)

    weighted_score = 0
    total_weight = 0
    for section, weight in SECTION_WEIGHTS.items():
        score = section_scores.get(section, 0)
        if sections.get(section, '').strip():
            weighted_score += score * weight
            total_weight += weight

    jd_score = round(weighted_score / total_weight) if total_weight > 0 else 0
    jd_score = round((jd_score * 0.7) + (overall_semantic * 100 * 0.3))

    resume_lower = resume_text.lower()
    matched_keywords = [kw for kw in jd_keywords if kw in resume_lower]
    missing_keywords = [kw for kw in jd_keywords if kw not in resume_lower]

    return jd_score, section_scores, matched_keywords, missing_keywords, overall_semantic


# ── Suggestions Generator ────────────────────────────────
def generate_suggestions(sections, quality_breakdown, section_scores,
                         resume_text, jd_keywords=None, has_jd=False):
    suggestions = []
    resume_lower = resume_text.lower()

    if quality_breakdown['action_verbs']['score'] < 10:
        suggestions.append(
            "Add more action verbs to your experience bullets — words like 'built', "
            "'optimized', 'reduced', 'led' make achievements sound stronger."
        )

    if quality_breakdown['quantification']['score'] < 9:
        suggestions.append(
            "Add more numbers to your resume — '500+ users', '30% faster', "
            "'3 critical processes'. Quantified achievements stand out to recruiters."
        )

    if quality_breakdown['summary_quality']['score'] < 7:
        suggestions.append(
            "Strengthen your professional summary — aim for 50+ words that clearly "
            "state your role, key skills, and what you're looking for."
        )

    if quality_breakdown['sections']['score'] < 16:
        suggestions.append(
            "Make sure your resume has all key sections: Summary, Skills, "
            "Experience, Projects, and Education."
        )

    if quality_breakdown['contact_info']['score'] < 8:
        suggestions.append(
            "Add complete contact info — email, phone, LinkedIn, and GitHub "
            "are all expected by recruiters."
        )

    if has_jd and jd_keywords:
        missing = [kw for kw in jd_keywords if kw not in resume_lower]
        if missing[:5]:
            suggestions.append(
                f"Add these keywords from the job description: {', '.join(missing[:5])}"
            )

        exp_score = section_scores.get('experience', 0) if section_scores else 0
        if exp_score < 50:
            suggestions.append(
                "Your experience section has low relevance to this job. "
                "Tailor your bullet points to match the job description."
            )

    return suggestions[:5]


# ── Main Analyzer ────────────────────────────────────────
def analyze_resume(pdf_path, job_description=None):
    resume_text = extract_text_from_pdf(pdf_path)
    sections = parse_sections(resume_text)

    # Always score quality
    quality_score, quality_breakdown = score_resume_quality(resume_text, sections)

    has_jd = bool(job_description and job_description.strip())

    if has_jd:
        # Try Groq first
        groq_result = groq_jd_match(resume_text, job_description)
        jd_score, matched_keywords, missing_keywords, section_scores, ai_suggestions = groq_result

        if jd_score is not None:
            # Groq succeeded
            overall_score = round((quality_score * 0.4) + (jd_score * 0.6))
            semantic_sim = jd_score / 100

            quality_suggestions = generate_suggestions(
                sections, quality_breakdown, section_scores,
                resume_text, has_jd=False
            )
            suggestions = ai_suggestions[:3] + [
                s for s in quality_suggestions if s not in ai_suggestions
            ][:2]

        else:
            # Fall back to TF-IDF
            jd_score, section_scores, matched_keywords, missing_keywords, semantic_sim = \
                score_jd_match(resume_text, job_description, sections)
            overall_score = round((quality_score * 0.6) + (jd_score * 0.4))
            suggestions = generate_suggestions(
                sections, quality_breakdown, section_scores,
                resume_text, extract_keywords(job_description, 40), has_jd=True
            )

    else:
        jd_score = None
        section_scores = {s: 0 for s in SECTION_WEIGHTS}
        matched_keywords = []
        missing_keywords = []
        semantic_sim = 0.0
        overall_score = quality_score
        suggestions = generate_suggestions(
            sections, quality_breakdown, {},
            resume_text, has_jd=False
        )

    return {
        'overall_score': overall_score,
        'quality_score': quality_score,
        'jd_match_score': jd_score,
        'quality_breakdown': quality_breakdown,
        'section_scores': section_scores,
        'matched_keywords': matched_keywords,
        'missing_keywords': missing_keywords,
        'semantic_similarity': semantic_sim,
        'suggestions': suggestions,
        'resume_text': resume_text,
        'has_jd': has_jd,
    }