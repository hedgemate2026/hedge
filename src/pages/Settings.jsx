import React, { useState, useEffect } from 'react';
import { User, Bell, Shield, Database, Moon, Sun, Monitor, X } from 'lucide-react';
import { Button } from '../components/Button';
import './Settings.css';

export const Settings = () => {
  const [profile, setProfile] = useState(() => JSON.parse(localStorage.getItem('hm_profile')) || {
    name: 'Premium User',
    email: 'premium.user@hedgemate.io'
  });
  
  const [notificationsEnabled, setNotificationsEnabled] = useState(() => JSON.parse(localStorage.getItem('hm_notif')) ?? true);
  const [emailAlerts, setEmailAlerts] = useState(() => JSON.parse(localStorage.getItem('hm_email')) ?? false);
  const [theme, setTheme] = useState(() => localStorage.getItem('hm_theme') || 'dark');
  
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editName, setEditName] = useState(profile.name);
  const [editEmail, setEditEmail] = useState(profile.email);

  useEffect(() => {
    document.documentElement.className = theme === 'light' ? 'light-mode' : '';
    localStorage.setItem('hm_theme', theme);
  }, [theme]);

  useEffect(() => { localStorage.setItem('hm_notif', JSON.stringify(notificationsEnabled)); }, [notificationsEnabled]);
  useEffect(() => { localStorage.setItem('hm_email', JSON.stringify(emailAlerts)); }, [emailAlerts]);
  useEffect(() => { localStorage.setItem('hm_profile', JSON.stringify(profile)); }, [profile]);

  const handleProfileSave = () => {
    setProfile({ name: editName, email: editEmail });
    setIsModalOpen(false);
  };

  const handleOpenModal = () => {
    setEditName(profile.name);
    setEditEmail(profile.email);
    setIsModalOpen(true);
  };

  return (
    <div className="settings-page">
      <div className="report-header mb-8">
        <span className="text-secondary text-xs font-semibold tracking-wider flex items-center gap-2">
          <span className="badge-purple">PREFERENCES</span>
          • User Settings
        </span>
        <h1 className="mt-2 mb-2">환경 설정</h1>
        <p className="text-secondary text-sm">계정 정보 관리, 알림 수신 설정 및 테마를 변경할 수 있습니다.</p>
      </div>

      <div className="settings-grid">
        <div className="card-box mb-6">
          <div className="card-header mb-6">
            <span className="icon-wrapper bg-dark"><User size={16}/></span>
            <span className="font-semibold">프로필 정보</span>
          </div>
          <div className="flex gap-6 items-center">
            <div className="settings-avatar">{profile.name.charAt(0).toUpperCase()}</div>
            <div className="flex-1">
              <div className="text-lg font-semibold">{profile.name}</div>
              <div className="text-sm text-secondary">{profile.email}</div>
              <div className="text-xs text-accent-light mt-1">HedgeMate Pro Plan (갱신일: 2026-12-31)</div>
            </div>
            <Button variant="outline" className="text-sm" onClick={handleOpenModal}>프로필 수정</Button>
          </div>
        </div>

        <div className="flex gap-6">
          <div className="card-box flex-1">
            <div className="card-header mb-6">
              <span className="icon-wrapper bg-dark"><Bell size={16}/></span>
              <span className="font-semibold">알림 설정</span>
            </div>
            <div className="setting-row" style={{cursor: 'pointer'}} onClick={() => setNotificationsEnabled(!notificationsEnabled)}>
              <div>
                <div className="font-medium">푸시 알림 수신</div>
                <div className="text-xs text-secondary mt-1">위험 자산 감지 시 브라우저 알림을 받습니다.</div>
              </div>
              <label className="toggle-switch" onClick={e => e.stopPropagation()}>
                <input type="checkbox" checked={notificationsEnabled} onChange={() => setNotificationsEnabled(!notificationsEnabled)} />
                <span className="slider"></span>
              </label>
            </div>
            <div className="setting-row mt-4" style={{cursor: 'pointer'}} onClick={() => setEmailAlerts(!emailAlerts)}>
              <div>
                <div className="font-medium">이메일 리포트 요약</div>
                <div className="text-xs text-secondary mt-1">매주 월요일 시장 요약 리포트를 이메일로 받습니다.</div>
              </div>
              <label className="toggle-switch" onClick={e => e.stopPropagation()}>
                <input type="checkbox" checked={emailAlerts} onChange={() => setEmailAlerts(!emailAlerts)} />
                <span className="slider"></span>
              </label>
            </div>
          </div>

          <div className="card-box flex-1">
            <div className="card-header mb-6">
              <span className="icon-wrapper bg-dark"><Database size={16}/></span>
              <span className="font-semibold">테마 및 디스플레이</span>
            </div>
            <div className="theme-options flex gap-3 mt-4">
              <div className={`theme-btn ${theme === 'dark' ? 'active' : ''}`} onClick={() => setTheme('dark')}>
                <Moon size={18} />
                <span>Dark</span>
              </div>
              <div className={`theme-btn ${theme === 'light' ? 'active' : ''}`} onClick={() => setTheme('light')}>
                <Sun size={18} />
                <span>Light</span>
              </div>
              <div className={`theme-btn ${theme === 'system' ? 'active' : ''}`} onClick={() => setTheme('system')}>
                <Monitor size={18} />
                <span>System</span>
              </div>
            </div>
            <p className="text-xs text-secondary mt-6">
              현재 버전은 다크 테마에 최적화되어 있습니다. 다른 테마 선택 시 일부 UI가 어색할 수 있습니다.
            </p>
          </div>
        </div>
      </div>

      {isModalOpen && (
        <div className="modal-overlay">
          <div className="modal-content card-box">
            <div className="flex justify-between items-center mb-6">
              <h3 className="font-semibold text-lg">프로필 수정</h3>
              <button onClick={() => setIsModalOpen(false)} style={{color: 'var(--text-secondary)'}}><X size={20}/></button>
            </div>
            <div className="form-group mb-4">
              <label>이름</label>
              <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} />
            </div>
            <div className="form-group mb-6">
              <label>이메일</label>
              <input type="email" value={editEmail} onChange={(e) => setEditEmail(e.target.value)} />
            </div>
            <div className="flex gap-3 justify-end">
              <Button variant="outline" onClick={() => setIsModalOpen(false)}>취소</Button>
              <Button variant="primary" onClick={handleProfileSave}>저장하기</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
