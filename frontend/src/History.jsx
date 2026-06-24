import { useState, useEffect } from 'react'
import axios from 'axios'
import API_URL from './config.js'

function History() {
  const [scans, setScans] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    const fetchHistory = async () => {
      try {
        const token = localStorage.getItem('access_token')
        const response = await axios.get(`${API_URL}/api/history/`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        setScans(response.data)
      } catch (err) {
        console.error(err)
        setError('Could not load history. Make sure the backend server is running.')
      } finally {
        setLoading(false)
      }
    }
    fetchHistory()
  }, [])

  const scoreClass = (score) => {
    if (score >= 75) return 'good'
    if (score >= 50) return 'ok'
    return 'low'
  }

  const scoreLabel = (score) => {
    if (score >= 75) return 'Strong'
    if (score >= 50) return 'Moderate'
    return 'Weak'
  }

  if (loading) {
    return (
      <div className="page-wrapper">
        <div className="page-inner">
          <div className="page-body">
            <div className="loading-overlay">
              <div className="spinner"></div>
              <p>Loading your scan history…</p>
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="page-wrapper">
      <div className="page-inner">
        <div className="page-hero">
          <h1>Scan <span>History</span></h1>
          <p>Review your past resume scans and track your improvement.</p>
        </div>

        <div className="page-body">
          {error && (
            <div className="error-msg">
              <span>⚠️</span> {error}
            </div>
          )}

          {!error && scans.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '3rem 2rem' }}>
              <p style={{ fontSize: '2.5rem', marginBottom: '1rem' }}>📄</p>
              <p style={{ fontWeight: 600, fontSize: '1rem', color: 'var(--text-1)', marginBottom: '0.4rem' }}>No scans yet</p>
              <p style={{ color: 'var(--text-2)', fontSize: '0.9rem' }}>Head back to the home page and check your first resume.</p>
            </div>
          ) : (
            <div className="history-list">
              {scans.map((scan) => (
                <div key={scan.id} className="history-card">
                  <div className="history-left">
                    <div className="history-icon">📄</div>
                    <div>
                      <p className="history-filename">{scan.resume_file_name}</p>
                      <p className="history-date">{new Date(scan.created_at).toLocaleString()}</p>
                    </div>
                  </div>
                  <div>
                    <div className={`history-score ${scoreClass(scan.score)}`}>
                      {scan.score}%
                    </div>
                    <div style={{ fontSize: '0.7rem', textAlign: 'center', color: 'var(--text-3)', marginTop: '0.2rem' }}>
                      {scoreLabel(scan.score)}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default History