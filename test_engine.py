from resume_scorer.ats_engine import analyze_resume, extract_text_from_pdf, parse_sections

jd = """
We are hiring a Junior Python Developer to join our backend engineering team.
Responsibilities include building REST APIs using Django and Django REST Framework,
working with PostgreSQL databases, collaborating with React.js frontend developers,
writing clean Python code following OOP principles, debugging existing codebases,
using Git for version control, and participating in code reviews.
Requirements: Strong Python knowledge, Django or Flask experience, REST API design,
SQL and PostgreSQL, basic React.js, Git workflows, debugging skills,
Bachelor's degree in Computer Science or related field.
"""

result = analyze_resume("Resume_Bala_Subramanyam.pdf", jd)

print(f"\n Overall Score: {result['overall_score']}%")
print(f" Semantic Similarity: {result['semantic_similarity']}")
print(f"\n Section Scores:")
for section, score in result['section_scores'].items():
    print(f"   {section.capitalize()}: {score}%")
print(f"\n Matched Keywords ({len(result['matched_keywords'])}):")
print(f"   {result['matched_keywords']}")
print(f"\n Missing Keywords ({len(result['missing_keywords'])}):")
print(f"   {result['missing_keywords']}")
print(f"\n Suggestions:")
for i, s in enumerate(result['suggestions'], 1):
    print(f"   {i}. {s}")

# ── Section detection debug ──────────────────────────────
print("\n--- Section Detection Debug ---")
text = extract_text_from_pdf("Resume_Bala_Subramanyam.pdf")
sections = parse_sections(text)
print("\nDetected sections:")
for name, content in sections.items():
    word_count = len(content.split())
    print(f"  {name}: {word_count} words")