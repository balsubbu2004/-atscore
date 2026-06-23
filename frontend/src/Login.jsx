import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import axios from 'axios'
import { GoogleLogin } from '@react-oauth/google'
import { useAuth } from './AuthContext.jsx'

function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await axios.post('http://localhost:8080/api/auth/login/', {
        username,
        password,
      })

      const { access, refresh } = response.data

      const meResponse = await axios.get('http://localhost:8080/api/auth/me/', {
        headers: { Authorization: `Bearer ${access}` }
      })

      login(access, refresh, meResponse.data)
      navigate('/')
    } catch (err) {
      console.error(err)
      setError('Invalid username or password.')
    } finally {
      setLoading(false)
    }
  }

  const handleGoogleSuccess = async (credentialResponse) => {
    try {
      const response = await axios.post('http://localhost:8080/api/auth/google/', {
        token: credentialResponse.credential
      })
      const { access, refresh, user } = response.data
      login(access, refresh, user)
      navigate('/')
    } catch (err) {
      console.error(err)
      setError('Google login failed. Please try again.')
    }
  }

  const handleGoogleError = () => {
    setError('Google login failed. Please try again.')
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-logo">
          <h1>⚡ ATScore</h1>
          <p>Sign in to your account</p>
        </div>

        <form onSubmit={handleSubmit} className="auth-form">
          <div className="form-group">
            <label className="field-label">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="Enter your username"
              required
            />
          </div>
          <div className="form-group">
            <label className="field-label">Password</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              required
            />
          </div>

          <div className="divider"><span>or continue with Google</span></div>

          <div className="google-btn-wrapper" style={{ marginBottom: '0.875rem' }}>
          <GoogleLogin
            onSuccess={handleGoogleSuccess}
            onError={handleGoogleError}
            text="continue_with"
            shape="rectangular"
            width="340"
          />
          </div>

          <button type="submit" className="btn-primary" disabled={loading} style={{ marginTop: '0.25rem', width: '100%' }}>
            {loading ? 'Signing in…' : 'Sign in'}
          </button>
        </form>

        {error && (
          <div className="error-msg" style={{ marginTop: '0.75rem' }}>
            <span>⚠️</span> {error}
          </div>
        )}

        <p className="auth-footer">
          Don't have an account? <Link to="/signup">Sign up free</Link>
        </p>
      </div>
    </div>
  )
}

export default Login