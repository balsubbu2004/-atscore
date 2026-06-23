import re
import pdfplumber
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer, util

# Load model once at startup — not on every request
model = SentenceTransformer('all-MiniLM-L6-v2')

# ── Section detection ────────────────────────────────────
SECTION_PATTERNS = {
    'summary': r'(professional\s+summary|summary|objective|profile|about\s+me)',
    'skills': r'(technical\s+skills|skills|technologies|competencies|expertise)',
    'experience': r'(experience|work\s+experience|employment|internship|career)',
    'projects': r'(projects|personal\s+projects|academic\s+projects|portfolio)',
    'education': r'(education|academic|qualifications|degrees)',
    'certifications': r'(certifications?|certificates?|courses?|training)',
}

SECTION_WEIGHTS = {
    'skills': 0.30,
    'experience': 0.25,
    'projects': 0.20,
    'summary': 0.15,
    'education': 0.07,
    'certifications': 0.03,
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
            ngram_range=(1, 2),
            max_features=max_features
        )
        vectorizer.fit([text])
        return vectorizer.get_feature_names_out().tolist()
    except Exception:
        return []


# ── Semantic Similarity ──────────────────────────────────
def semantic_similarity(text1, text2):
    if not text1.strip() or not text2.strip():
        return 0.0
    emb1 = model.encode(text1, convert_to_tensor=True)
    emb2 = model.encode(text2, convert_to_tensor=True)
    score = util.cos_sim(emb1, emb2).item()
    return round(max(0.0, min(1.0, score)), 4)


# ── Section Scorer ───────────────────────────────────────
def score_section(section_text, jd_text, jd_keywords):
    if not section_text.strip():
        return 0

    # Keyword match score (50% of section score)
    section_lower = section_text.lower()
    matched = [kw for kw in jd_keywords if kw in section_lower]
    keyword_score = (len(matched) / len(jd_keywords) * 100) if jd_keywords else 0

    # Semantic similarity score (50% of section score)
    sem_score = semantic_similarity(section_text, jd_text) * 100

    # Combined
    return round((keyword_score * 0.5) + (sem_score * 0.5))


# ── Suggestions Generator ────────────────────────────────
def generate_suggestions(sections, jd_keywords, section_scores, resume_text):
    suggestions = []
    resume_lower = resume_text.lower()

    # Skills suggestions
    missing_keywords = [kw for kw in jd_keywords if kw not in resume_lower]
    if missing_keywords[:5]:
        top_missing = ', '.join(missing_keywords[:5])
        suggestions.append(
            f"Add these missing skills to your resume: {top_missing}"
        )

    # Experience suggestions
    exp_score = section_scores.get('experience', 0)
    if exp_score < 50:
        suggestions.append(
            "Your experience section has low relevance to this job. "
            "Add more quantified achievements and use keywords from the job description."
        )
    elif exp_score < 70:
        suggestions.append(
            "Strengthen your experience section by adding metrics and impact "
            "(e.g. 'reduced load time by 30%', 'handled 500+ users')."
        )

    # Projects suggestions
    proj_score = section_scores.get('projects', 0)
    if proj_score < 50:
        suggestions.append(
            "Your projects section doesn't align well with this role. "
            "Highlight projects that use technologies mentioned in the job description."
        )

    # Summary suggestions
    if not sections.get('summary', '').strip():
        suggestions.append(
            "Add a professional summary at the top of your resume "
            "that directly mentions the role you're applying for."
        )
    elif section_scores.get('summary', 0) < 50:
        suggestions.append(
            "Rewrite your summary to better match this role — "
            "mention the job title and key skills from the job description."
        )

    # Certifications
    if not sections.get('certifications', '').strip():
        suggestions.append(
            "Consider adding relevant certifications to strengthen your profile "
            "for this role."
        )

    # Education
    edu_score = section_scores.get('education', 0)
    if edu_score < 40:
        suggestions.append(
            "Your education section may not match the requirements. "
            "Check if the JD mentions specific degree requirements."
        )

    return suggestions[:5]  # max 5 suggestions


# ── Main Analyzer ────────────────────────────────────────
def analyze_resume(pdf_path, job_description):
    # Extract text
    resume_text = extract_text_from_pdf(pdf_path)

    # Parse into sections
    sections = parse_sections(resume_text)

    # Extract JD keywords
    jd_keywords = extract_keywords(job_description, max_features=40)

    # Score each section
    section_scores = {}
    for section in SECTION_WEIGHTS:
        section_scores[section] = score_section(
            sections.get(section, ''),
            job_description,
            jd_keywords
        )

    # Overall weighted score
    overall_score = 0
    total_weight = 0
    for section, weight in SECTION_WEIGHTS.items():
        score = section_scores.get(section, 0)
        if sections.get(section, '').strip():
            overall_score += score * weight
            total_weight += weight

    if total_weight > 0:
        overall_score = round(overall_score / total_weight)
    else:
        overall_score = 0

    # Overall semantic similarity
    overall_semantic = semantic_similarity(resume_text, job_description)

    # Blend overall score with semantic similarity
    overall_score = round((overall_score * 0.6) + (overall_semantic * 100 * 0.4))

    # Keyword matching for display
    resume_lower = resume_text.lower()
    matched_keywords = [kw for kw in jd_keywords if kw in resume_lower]
    missing_keywords = [kw for kw in jd_keywords if kw not in resume_lower]

    # Generate suggestions
    suggestions = generate_suggestions(
        sections, jd_keywords, section_scores, resume_text
    )

    return {
        'overall_score': overall_score,
        'section_scores': section_scores,
        'matched_keywords': matched_keywords,
        'missing_keywords': missing_keywords,
        'semantic_similarity': overall_semantic,
        'suggestions': suggestions,
        'resume_text': resume_text,
    }