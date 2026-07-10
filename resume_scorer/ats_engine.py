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


# ── Groq AI Quality Scorer ───────────────────────────────
def groq_quality_score(resume_text):
    api_key = os.getenv('GROQ_API_KEY')

    if not api_key:
        return None, {}, []

    try:
        client = Groq(api_key=api_key)

        prompt = f"""You are a strict ATS (Applicant Tracking System) and professional resume evaluator.

Evaluate this resume like a real ATS system would — be honest and realistic, not generous.

RESUME:
{resume_text[:3000]}

Score each category strictly. A perfect score means industry-level quality. Most fresher resumes score 60-80%.

Return ONLY this JSON with no explanation, no markdown, no code blocks:
{{
    "overall_quality_score": <integer 0-100, be realistic and strict>,
    "quality_breakdown": {{
        "sections": {{
            "score": <integer 0-20>,
            "max": 20,
            "detail": "<what sections are present and what's missing>"
        }},
        "action_verbs": {{
            "score": <integer 0-15>,
            "max": 15,
            "detail": "<quality and strength of action verbs used>"
        }},
        "quantification": {{
            "score": <integer 0-15>,
            "max": 15,
            "detail": "<quality of quantified achievements — are they meaningful metrics?>"
        }},
        "contact_info": {{
            "score": <integer 0-10>,
            "max": 10,
            "detail": "<what contact fields are present>"
        }},
        "summary_quality": {{
            "score": <integer 0-10>,
            "max": 10,
            "detail": "<is the summary strong, specific, and targeted?>"
        }},
        "skills_depth": {{
            "score": <integer 0-10>,
            "max": 10,
            "detail": "<are skills relevant, specific, and well-organized?>"
        }},
        "projects_impact": {{
            "score": <integer 0-10>,
            "max": 10,
            "detail": "<do projects show real impact, tech stack, and outcomes?>"
        }},
        "experience_quality": {{
            "score": <integer 0-10>,
            "max": 10,
            "detail": "<quality and relevance of work experience>"
        }}
    }},
    "suggestions": [<list of 3-5 specific actionable improvement suggestions>],
    "strengths": [<list of 2-3 things the resume does well>]
}}"""

        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1500,
        )

        raw = response.choices[0].message.content.strip()
        raw = re.sub(r'```json|```', '', raw).strip()

        data = json.loads(raw)

        return (
            data.get('overall_quality_score', 0),
            data.get('quality_breakdown', {}),
            data.get('suggestions', []),
            data.get('strengths', [])
        )

    except json.JSONDecodeError as e:
        return None, {}, [], []
    except Exception as e:
        return None, {}, [], []


# ── Rule-based Quality Scorer (fallback) ─────────────────
def rule_based_quality_score(resume_text, sections):
    quality_breakdown = {}
    resume_lower = resume_text.lower()
    word_count = len(resume_text.split())

    ACTION_VERBS = [
        'built', 'developed', 'implemented', 'designed', 'created', 'led',
        'managed', 'optimized', 'improved', 'reduced', 'increased', 'delivered',
        'architected', 'deployed', 'integrated', 'automated', 'debugged', 'fixed',
        'collaborated', 'contributed', 'analyzed', 'identified', 'resolved',
        'established', 'launched', 'migrated', 'refactored', 'tested', 'documented',
        'trained', 'mentored', 'coordinated', 'streamlined', 'maintained'
    ]

    # 1. Section completeness (20 points)
    key_sections = ['summary', 'skills', 'experience', 'projects', 'education']
    found_sections = sum(1 for s in key_sections if sections.get(s, '').strip())
    section_score = round((found_sections / len(key_sections)) * 20)
    quality_breakdown['sections'] = {
        'score': section_score, 'max': 20,
        'detail': f'{found_sections}/{len(key_sections)} key sections found'
    }

    # 2. Action verbs (15 points)
    exp_text = sections.get('experience', '') + ' ' + sections.get('projects', '')
    found_verbs = [v for v in ACTION_VERBS if v in exp_text.lower()]
    verb_score = min(15, round((len(found_verbs) / 8) * 15))
    quality_breakdown['action_verbs'] = {
        'score': verb_score, 'max': 15,
        'detail': f'{len(found_verbs)} action verbs found'
    }

    # 3. Quantification (15 points)
    number_pattern = r'\b\d+[\+\%]?\s*(users?|students?|bugs?|languages?|months?|years?|hours?|k|million)?\b'
    numbers_found = re.findall(number_pattern, resume_lower)
    quant_score = min(15, len(numbers_found) * 3)
    quality_breakdown['quantification'] = {
        'score': quant_score, 'max': 15,
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
        'score': contact_score, 'max': 10,
        'detail': f'{contact_count}/4 contact fields present'
    }

    # 5. Summary (10 points)
    summary_words = len(sections.get('summary', '').split())
    summary_score = 10 if summary_words >= 50 else 7 if summary_words >= 30 else 4 if summary_words >= 10 else 0
    quality_breakdown['summary_quality'] = {
        'score': summary_score, 'max': 10,
        'detail': f'Summary has {summary_words} words'
    }

    # 6. Skills (10 points)
    skills_count = len([s for s in re.split(r'[,\n|]', sections.get('skills', '')) if s.strip()])
    skills_score = min(10, round((skills_count / 10) * 10))
    quality_breakdown['skills_depth'] = {
        'score': skills_score, 'max': 10,
        'detail': f'{skills_count} skills listed'
    }

    # 7. Projects (10 points)
    tech_keywords = ['python', 'django', 'flask', 'react', 'javascript', 'postgresql',
                     'sql', 'api', 'git', 'docker', 'linux', 'sqlite']
    techs_in_projects = [t for t in tech_keywords if t in sections.get('projects', '').lower()]
    projects_score = min(10, len(techs_in_projects) * 2)
    quality_breakdown['projects_impact'] = {
        'score': projects_score, 'max': 10,
        'detail': f'{len(techs_in_projects)} technologies mentioned in projects'
    }

    # 8. Experience (10 points)
    exp_words = len(sections.get('experience', '').split())
    exp_score = 10 if exp_words >= 80 else 7 if exp_words >= 40 else 4 if exp_words >= 20 else 0
    quality_breakdown['experience_quality'] = {
        'score': exp_score, 'max': 10,
        'detail': f'Experience section has {exp_words} words'
    }

    total = sum(v['score'] for v in quality_breakdown.values())
    return total, quality_breakdown


# ── Groq AI JD Matcher ───────────────────────────────────
def groq_jd_match(resume_text, job_description):
    api_key = os.getenv('GROQ_API_KEY')

    if not api_key:
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
        raw = re.sub(r'```json|```', '', raw).strip()
        data = json.loads(raw)

        return (
            data.get('jd_match_score', 0),
            data.get('matched_skills', []),
            data.get('missing_skills', []),
            data.get('section_scores', {}),
            data.get('suggestions', [])
        )

    except json.JSONDecodeError:
        return None, [], [], {}, []
    except Exception:
        return None, [], [], {}, []


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


# ── Main Analyzer ────────────────────────────────────────
def analyze_resume(pdf_path, job_description=None):
    resume_text = extract_text_from_pdf(pdf_path)
    sections = parse_sections(resume_text)

    has_jd = bool(job_description and job_description.strip())

    # Try Groq quality scoring first
    groq_quality_result = groq_quality_score(resume_text)
    quality_score, quality_breakdown, quality_suggestions, strengths = groq_quality_result

    if quality_score is None:
        # Fall back to rule-based
        quality_score, quality_breakdown = rule_based_quality_score(resume_text, sections)
        quality_suggestions = []
        strengths = []

    if has_jd:
        # Try Groq JD matching
        groq_result = groq_jd_match(resume_text, job_description)
        jd_score, matched_keywords, missing_keywords, section_scores, jd_suggestions = groq_result

        if jd_score is not None:
            overall_score = round((quality_score * 0.4) + (jd_score * 0.6))
            semantic_sim = jd_score / 100
            suggestions = jd_suggestions[:3] + quality_suggestions[:2]
        else:
            # TF-IDF fallback
            jd_score, section_scores, matched_keywords, missing_keywords, semantic_sim = \
                score_jd_match(resume_text, job_description, sections)
            overall_score = round((quality_score * 0.6) + (jd_score * 0.4))
            suggestions = quality_suggestions
    else:
        jd_score = None
        section_scores = {s: 0 for s in SECTION_WEIGHTS}
        matched_keywords = []
        missing_keywords = []
        semantic_sim = 0.0
        overall_score = quality_score
        suggestions = quality_suggestions

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
        'strengths': strengths,
        'resume_text': resume_text,
        'has_jd': has_jd,
    }