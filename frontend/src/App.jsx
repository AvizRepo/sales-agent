import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import CompanyLogin from './components/CompanyLogin';
import CompanyDashboard from './components/CompanyDashboard';
import UserLogin from './components/UserLogin';
import UserCallRequestPage from './components/UserCallRequestPage';
import './App.css';

const ProtectedCompanyRoute = ({ children }) => {
  const isCompanyLoggedIn = localStorage.getItem('isCompanyLoggedIn') === 'true';
  return isCompanyLoggedIn ? children : <Navigate to="/company-login" replace />;
};

const ProtectedUserRoute = ({ children }) => {
  const isUserLoggedIn = localStorage.getItem('isUserLoggedIn') === 'true';
  return isUserLoggedIn ? children : <Navigate to="/" replace />;
};

function App() {
  return (
    <Router>
      <div>
        <Routes>
          <Route path="/" element={<UserLogin />} />
          <Route path="/company-login" element={<CompanyLogin />} />
          <Route
            path="/company-dashboard"
            element={
              <ProtectedCompanyRoute>
                <CompanyDashboard />
              </ProtectedCompanyRoute>
            }
          />
          <Route
            path="/request-call"
            element={
              <ProtectedUserRoute>
                <UserCallRequestPage />
              </ProtectedUserRoute>
            }
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </Router>
  );
}

export default App;