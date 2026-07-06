from dotenv import load_dotenv
load_dotenv()
from resume_scorer.ats_engine import analyze_resume

# Test 1 — no JD
print("=== TEST 1: No JD ===")
result = analyze_resume("Resume_Bala_Subramanyam.pdf")
print(f"Overall Score: {result['overall_score']}%")
print(f"Quality Score: {result['quality_score']}%")
print(f"Suggestions: {result['suggestions']}")

# Test 2 — with JD
print("\n=== TEST 2: With JD ===")
jd = "Python Django REST API PostgreSQL Git React OOP debugging Linux authentication"
result2 = analyze_resume("Resume_Bala_Subramanyam.pdf", jd)
print(f"Overall Score: {result2['overall_score']}%")
print(f"Quality Score: {result2['quality_score']}%")
print(f"JD Match Score: {result2['jd_match_score']}%")
print(f"Suggestions: {result2['suggestions']}")

print(f"Section scores: {result2['section_scores']}")
print(f"Matched keywords: {result2['matched_keywords']}")
print(f"Missing keywords: {result2['missing_keywords']}")