import { Navigate } from 'react-router-dom'
import { useAuth } from './AuthContext.jsx'

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()

  if (loading) {
    return <p className="subtitle" style={{ textAlign: 'center', marginTop: '2rem' }}>Loading...</p>
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  return children
}

export default ProtectedRoute