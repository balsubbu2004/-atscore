import { useState } from 'react'
import { Routes, Route, Link, useNavigate } from 'react-router-dom'
import axios from 'axios'
import History from './History.jsx'
import Login from './Login.jsx'
import Signup from './Signup.jsx'
import ProtectedRoute from './ProtectedRoute.jsx'
import { useAuth } from './AuthContext.jsx'
import './App.css'

function ScoreForm() {
  const [resumeFile, setResumeFile] = useState(null)
  const [jobDescription, setJobDescription] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleFileChange = (e) => {
    setResumeFile(e.target.files[0])
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')

    if (!resumeFile || !jobDescription.trim()) {
      setError('Please upload a resume and paste a job description.')
      return
    }

    const formData = new FormData()
    formData.append('resume', resumeFile)
    formData.append('job_description', jobDescription)

    setLoading(true)
    setResult(null)

    try {
      const token = localStorage.getItem('access_token')
      const response = await axios.post(
        '${import.meta.env.VITE_API_URL}/api/score/',
        formData,
        {
          headers: {
            'Content-Type': 'multipart/form-data',
            Authorization: `Bearer ${token}`,
          }
        }
      )
      setResult(response.data)
    } catch (err) {
      console.error(err)
      setError('Something went wrong. Make sure the backend server is running.')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setResumeFile(null)
    setJobDescription('')
    setResult(null)
    setError('')
    document.getElementById('resume-input').value = ''
  }

  const getScoreLabel = (score) => {
    if (score >= 75) return 'Strong match'
    if (score >= 50) return 'Moderate match'
    return 'Weak match'
  }

  const getScoreColor = (score) => {
    if (score >= 75) return 'var(--success)'
    if (score >= 50) return '#f59e0b'
    return 'var(--danger)'
  }

  const sectionLabels = {
    skills: '🛠 Skills',
    experience: '💼 Experience',
    projects: '🚀 Projects',
    summary: '📝 Summary',
    education: '🎓 Education',
    certifications: '📜 Certifications',
  }

  return (
    <div className={`scorer-page ${result || loading ? 'split' : 'centered'}`}>

      {/* ── Left / Center panel ── */}
      <div className="scorer-left">
        <div className="page-hero" style={{ borderRadius: 'var(--radius-lg) var(--radius-lg) 0 0' }}>
          <h1>ATS Resume <span>Scorer</span></h1>
          <p>Upload your resume and paste a job description to get an instant match score.</p>
        </div>

        <div className="scorer-form-body">
          <form onSubmit={handleSubmit} className="upload-form">
            <div>
              <label className="field-label">Resume (PDF)</label>
              <div className={`file-drop-zone ${resumeFile ? 'has-file' : ''}`}>
                <input
                  id="resume-input"
                  type="file"
                  accept=".pdf"
                  onChange={handleFileChange}
                />
                <span className="drop-icon">{resumeFile ? '✅' : '📄'}</span>
                {resumeFile ? (
                  <div className="file-name-badge">✓ {resumeFile.name}</div>
                ) : (
                  <>
                    <p className="drop-label">Drop your resume here or click to browse</p>
                    <p className="drop-hint">PDF only · max 5 MB</p>
                  </>
                )}
              </div>
            </div>

            <div>
              <label className="field-label">Job Description</label>
              <textarea
                rows="4"
                placeholder="Paste the full job description here…"
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
              />
            </div>

            <div className="button-row">
              <button type="submit" className="btn-primary" disabled={loading}>
                {loading ? 'Analyzing…' : 'Check my score'}
              </button>
              {(result || resumeFile || jobDescription) && (
                <button type="button" className="btn-outline" onClick={handleReset}>
                  Start over
                </button>
              )}
            </div>
          </form>

          {error && (
            <div className="error-msg" style={{ marginTop: '1rem' }}>
              <span>⚠️</span> {error}
            </div>
          )}
        </div>
      </div>

      {/* ── Right panel — only shown after scoring ── */}
      {(result || loading) && (
        <div className="scorer-right">
          {loading && (
            <div className="scorer-empty">
              <div className="spinner" style={{ margin: '0 auto 1rem' }}></div>
              <p style={{ color: 'var(--text-2)' }}>Analyzing your resume…</p>
            </div>
          )}

          {result && (
            <div className="result-scroll">

              {/* Overall Score */}
              <div className="result-header">
                <div className="score-ring-wrap">
                  <div className="score-circle">
                    <span className="score-number">{result.overall_score}</span>
                    <span className="score-label">/ 100</span>
                  </div>
                </div>
                <h2>{getScoreLabel(result.overall_score)}</h2>
                <p style={{ color: '#94a3b8', fontSize: '0.85rem', marginTop: '0.25rem' }}>
                  Semantic similarity: {Math.round(result.semantic_similarity * 100)}%
                </p>
              </div>

              {/* Score Bar */}
              <div className="score-bar-wrap">
                <div className="score-bar-track">
                  <div className="score-bar-fill" style={{ width: `${result.overall_score}%` }} />
                </div>
                <div className="score-bar-labels">
                  <span>Weak</span>
                  <span>Moderate</span>
                  <span>Strong</span>
                </div>
              </div>

              {/* Section Scores */}
              <div className="section-scores-wrap">
                <h3 className="section-scores-title">Section Breakdown</h3>
                <div className="section-scores-grid">
                  {Object.entries(result.section_scores).map(([section, score]) => (
                    <div key={section} className="section-score-item">
                      <div className="section-score-top">
                        <span className="section-score-label">
                          {sectionLabels[section] || section}
                        </span>
                        <span
                          className="section-score-value"
                          style={{ color: getScoreColor(score) }}
                        >
                          {score}%
                        </span>
                      </div>
                      <div className="section-bar-track">
                        <div
                          className="section-bar-fill"
                          style={{
                            width: `${score}%`,
                            background: getScoreColor(score)
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Suggestions */}
              {result.suggestions && result.suggestions.length > 0 && (
                <div className="suggestions-wrap">
                  <h3 className="suggestions-title">💡 Improvement Suggestions</h3>
                  <ul className="suggestions-list">
                    {result.suggestions.map((suggestion, i) => (
                      <li key={i} className="suggestion-item">
                        <span className="suggestion-num">{i + 1}</span>
                        <span>{suggestion}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Keywords */}
              <div className="keyword-grid">
                <div className="keyword-col">
                  <div className="keyword-col-header">
                    <h3 style={{ color: 'var(--success)' }}>Matched</h3>
                    <span className="kw-count matched">{result.matched_keywords.length}</span>
                  </div>
                  <ul className="keyword-list">
                    {result.matched_keywords.map((kw, i) => (
                      <li key={i} className="keyword-pill matched">✓ {kw}</li>
                    ))}
                  </ul>
                </div>

                <div className="keyword-col">
                  <div className="keyword-col-header">
                    <h3 style={{ color: 'var(--danger)' }}>Missing</h3>
                    <span className="kw-count missing">{result.missing_keywords.length}</span>
                  </div>
                  <ul className="keyword-list">
                    {result.missing_keywords.map((kw, i) => (
                      <li key={i} className="keyword-pill missing">✗ {kw}</li>
                    ))}
                  </ul>
                </div>
              </div>

            </div>
          )}
        </div>
      )}
    </div>
  )
}

function Navbar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">⚡ ATScore</Link>
      {user && <Link to="/history">History</Link>}
      {user ? (
        <>
          <span className="navbar-user">👤 {user.username}</span>
          <button className="logout-btn" onClick={handleLogout}>Log out</button>
        </>
      ) : (
        <>
          <Link to="/login">Log in</Link>
          <Link to="/signup">Sign up</Link>
        </>
      )}
    </nav>
  )
}

function App() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={
          <ProtectedRoute>
            <ScoreForm />
          </ProtectedRoute>
        } />
        <Route path="/history" element={
          <ProtectedRoute>
            <History />
          </ProtectedRoute>
        } />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
      </Routes>
    </>
  )
}

export default App