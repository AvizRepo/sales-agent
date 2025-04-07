import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import './components.css';

function CompanyLogin() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const navigate = useNavigate();

  const handleLogin = (e) => {
    e.preventDefault();
    setError('');
    if (username === 'admin' && password === 'pass') {
      localStorage.setItem('isCompanyLoggedIn', 'true');
      localStorage.removeItem('isUserLoggedIn');
      navigate('/company-dashboard');
    } else {
      setError('Invalid credentials (Hint: admin/pass)');
    }
  };

  return (
    <div className="login-container">
      <h1>Admin Login</h1>
      <p style={{ textAlign: 'center', color: '#6b7280', marginBottom: '1.5rem' }}>
        Manage your AI agent
      </p>
      <form onSubmit={handleLogin}>
        <div className="form-group">
          <label>Username</label>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            placeholder="Enter username"
            required
          />
        </div>
        <div className="form-group">
          <label>Password</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="Enter password"
            required
          />
        </div>
        {error && <p className="error-message">{error}</p>}
        <button type="submit">Sign In</button>
      </form>
      <div style={{ textAlign: 'center', marginTop: '1.5rem' }}>
        <Link to="/" className="link-button">Back to User Login</Link>
      </div>
    </div>
  );
}

export default CompanyLogin;