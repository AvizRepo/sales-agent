import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './components.css';

function CompanyDashboard() {
  const [knowledgeText, setKnowledgeText] = useState('');
  const [savedKnowledge, setSavedKnowledge] = useState('');
  const [isEditingKnowledge, setIsEditingKnowledge] = useState(false);
  const [uploadStatus, setUploadStatus] = useState('');
  const [isUploading, setIsUploading] = useState(false);
  const [companyName, setCompanyName] = useState('');
  const [newCompanyName, setNewCompanyName] = useState('');
  const [companyNameStatus, setCompanyNameStatus] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    const isLoggedIn = localStorage.getItem('isCompanyLoggedIn') === 'true';
    if (!isLoggedIn) navigate('/company-login');
    else {
      fetchCompanyName();
      fetchKnowledgeSummary();
    }
  }, [navigate]);

  const fetchCompanyName = async () => {
    try {
      const response = await fetch('http://localhost:8000/company_info');
      if (response.ok) {
        const data = await response.json();
        setCompanyName(data.company_name || 'Not Set');
        setNewCompanyName(data.company_name || '');
      } else setCompanyNameStatus('Failed to fetch company name.');
    } catch (error) {
      setCompanyNameStatus(`Error: ${error.message}`);
    }
  };

  const fetchKnowledgeSummary = async () => {
    try {
      const response = await fetch('http://localhost:8000/get_knowledge');
      if (response.ok) {
        const data = await response.json();
        setSavedKnowledge(data.knowledge_summary);
        if (data.knowledge_summary === "No knowledge summary available.") {
          setSavedKnowledge('');
        }
      } else {
        setUploadStatus('No knowledge summary available.');
      }
    } catch (error) {
      setUploadStatus(`Error fetching knowledge: ${error.message}`);
    }
  };

  const handleUploadKnowledge = async () => {
    if (!knowledgeText.trim()) {
      setUploadStatus('Please enter knowledge text.');
      return;
    }
    setIsUploading(true);
    setUploadStatus('Processing...');
    try {
      const response = await fetch('http://localhost:8000/upload_knowledge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ knowledge_text: knowledgeText }),
      });
      const data = await response.json();
      setUploadStatus(response.ok ? 'Knowledge updated successfully!' : `Error: ${data.detail}`);
      if (response.ok) {
        setSavedKnowledge(knowledgeText);
        setKnowledgeText(''); 
        setIsEditingKnowledge(false);
        fetchKnowledgeSummary();
      }
    } catch (error) {
      setUploadStatus(`Error: ${error.message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const handleEditKnowledge = () => {
    setIsEditingKnowledge(true);
    setKnowledgeText(savedKnowledge);
  };

  const handleSetCompanyName = async () => {
    if (!newCompanyName.trim()) {
      setCompanyNameStatus('Company name cannot be empty.');
      return;
    }
    setCompanyNameStatus('Updating...');
    try {
      const response = await fetch('http://localhost:8000/company_info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: newCompanyName }),
      });
      const data = await response.json();
      setCompanyNameStatus(response.ok ? 'Company name updated!' : `Error: ${data.detail}`);
      if (response.ok) setCompanyName(newCompanyName);
    } catch (error) {
      setCompanyNameStatus(`Error: ${error.message}`);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('isCompanyLoggedIn');
    navigate('/company-login');
  };

  return (
    <div className="dashboard-container">
      <button onClick={handleLogout} className="logout-button">Logout</button>
      <h1>Admin Dashboard</h1>

      <div className="dashboard-section">
        <h2>Company</h2>
        <div className="form-group">
          <label>Company Name</label>
          <input
            type="text"
            value={newCompanyName}
            onChange={(e) => setNewCompanyName(e.target.value)}
            placeholder="Enter company name"
          />
        </div>
        <button onClick={handleSetCompanyName}>Update Name</button>
        {companyNameStatus && <div className="status">{companyNameStatus}</div>}
      </div>

      <div className="dashboard-section knowledge-section">
        <h2>Knowledge Base</h2>
        <div className="form-group">
          <label>AI Knowledge</label>
          {savedKnowledge && !isEditingKnowledge ? (
            <div className="knowledge-box">
              <pre>{savedKnowledge}</pre>
              <button onClick={handleEditKnowledge} className="edit-button">Edit</button>
            </div>
          ) : (
            <textarea
              value={knowledgeText}
              onChange={(e) => setKnowledgeText(e.target.value)}
              placeholder="Enter product details, sales info, etc."
              disabled={isUploading}
            />
          )}
        </div>
        {(isEditingKnowledge || !savedKnowledge) && (
          <button onClick={handleUploadKnowledge} disabled={isUploading}>
            {isUploading ? 'Processing...' : 'Update Knowledge'}
          </button>
        )}
        {uploadStatus && <div className="status">{uploadStatus}</div>}
      </div>

      <div className="dashboard-section">
        <h2>User Activity</h2>
        <ul>
          <li>User A - Last call: 3/28/2025</li>
          <li>User B - Last call: 3/27/2025</li>
        </ul>
      </div>
    </div>
  );
}

export default CompanyDashboard;