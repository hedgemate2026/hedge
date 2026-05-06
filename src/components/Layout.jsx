import React, { useState } from 'react';
import { Sidebar } from './Sidebar';
import { Search, Bell, User } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import './Layout.css';

export const Layout = ({ children }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const navigate = useNavigate();

  const handleSearch = (e) => {
    if (e.key === 'Enter' && searchTerm.trim() !== '') {
      navigate(`/analysis?q=${searchTerm}`);
      setSearchTerm('');
    }
  };

  return (
    <div className="layout">
      <Sidebar />
      <main className="main-content">
        <header className="topnav">
          <div style={{width: 200}}></div>{/* spacer */}
          <div className="topnav-search">
            <Search size={16} className="text-secondary" />
            <input 
              type="text" 
              placeholder="자산 검색..." 
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              onKeyDown={handleSearch}
            />
          </div>
          <div className="topnav-actions">
            <Bell size={20} style={{cursor:'pointer'}} />
            <User size={20} style={{cursor:'pointer'}} />
          </div>
        </header>
        <div className="page-content">
          {children}
        </div>
      </main>
    </div>
  );
};
