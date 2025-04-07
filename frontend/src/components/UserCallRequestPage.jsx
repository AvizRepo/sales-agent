import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import './components.css';

function UserCallRequestPage() {
  const [userName, setUserName] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [callStatus, setCallStatus] = useState('');
  const [callSid, setCallSid] = useState(null);
  const [isLoadingCall, setIsLoadingCall] = useState(false);
  const [conversationLog, setConversationLog] = useState(null);
  const [isFetchingLog, setIsFetchingLog] = useState(false);
  const [companyName, setCompanyName] = useState('Our Company');
  const navigate = useNavigate();

  useEffect(() => {
    const fetchInfo = async () => {
      const isLoggedIn = localStorage.getItem('isUserLoggedIn') === 'true';
      if (!isLoggedIn) {
        navigate('/');
        return;
      }
      try {
        const response = await fetch('http://localhost:8000/company_info');
        if (response.ok) {
          const data = await response.json();
          if (data.company_name && data.company_name !== 'Not Set') {
            setCompanyName(data.company_name);
          }
        }
      } catch (error) {
        console.error('Error fetching company name:', error);
      }
    };
    fetchInfo();
  }, [navigate]);

  const handleInitiateCall = async () => {
    if (!phoneNumber || !userName) {
      setCallStatus('Please enter your name and phone number.');
      return;
    }
    setIsLoadingCall(true);
    setCallStatus('Initiating call...');
    setCallSid(null);
    setConversationLog(null);
    try {
      const response = await fetch('http://localhost:8000/initiate_call', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ phone_number: phoneNumber, user_name: userName }),
      });
      const data = await response.json();
      if (response.ok && data.success) {
        setCallStatus(`Call initiated! Call SID: ${data.call_sid}`);
        setCallSid(data.call_sid);
      } else {
        setCallStatus(`Error: ${data.error || 'Failed to initiate call.'}`);
      }
    } catch (error) {
      setCallStatus(`Error: ${error.message}`);
    } finally {
      setIsLoadingCall(false);
    }
  };

  const handleFetchConversationLog = async () => {
    if (!callSid) {
      setConversationLog('No call SID available.');
      return;
    }
    setIsFetchingLog(true);
    setConversationLog('Fetching log...');
    try {
      const response = await fetch(`http://localhost:8000/get_conversation_history/${callSid}`);
      const data = await response.json();
      if (response.ok) {
        setConversationLog(data.formatted_text || 'No log available.');
      } else {
        setConversationLog(`Error: ${data.detail}`);
      }
    } catch (error) {
      setConversationLog(`Error: ${error.message}`);
    } finally {
      setIsFetchingLog(false);
    }
  };

  const handleUserLogout = () => {
    localStorage.removeItem('isUserLoggedIn');
    navigate('/');
  };

  return (
    <div className="user-call-page">
      <button onClick={handleUserLogout} className="logout-button">Logout</button>
      <h1>{companyName}</h1>
      <p style={{ textAlign: 'center', color: '#6b7280', marginBottom: '2rem' }}>
        Connect with our AI Agent
      </p>

      <div className="call-request-form">
        <div className="form-group">
          <label>Your Name</label>
          <input
            type="text"
            value={userName}
            onChange={(e) => setUserName(e.target.value)}
            placeholder="Jane Doe"
            disabled={isLoadingCall}
            required
          />
        </div>
        <div className="form-group">
          <label>Phone Number</label>
          <input
            type="tel"
            value={phoneNumber}
            onChange={(e) => setPhoneNumber(e.target.value)}
            placeholder="+15551234567"
            disabled={isLoadingCall}
            required
          />
        </div>
        <button onClick={handleInitiateCall} disabled={isLoadingCall}>
          {isLoadingCall ? 'Requesting...' : 'Request Call'}
        </button>
      </div>

      {callStatus && <div className="status">{callStatus}</div>}

      {callSid && (
        <div className="conversation-log-section">
          <h2>Call Log</h2>
          <button onClick={handleFetchConversationLog} disabled={isFetchingLog}>
            {isFetchingLog ? 'Fetching...' : 'View Log'}
          </button>
          {conversationLog && (
            <div className="conversation-log-result">
              <pre>{conversationLog}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default UserCallRequestPage;