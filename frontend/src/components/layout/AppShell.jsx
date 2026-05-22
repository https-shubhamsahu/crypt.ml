import React, { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import { useTheme } from '../../hooks/useTheme';
import { 
  Shield, 
  LayoutDashboard, 
  Cpu, 
  Table, 
  FileText, 
  MessageSquare, 
  Binary, 
  Sun, 
  Moon,
  Activity,
  Menu,
  X
} from 'lucide-react';

export default function AppShell({ children }) {
  const { theme, toggleTheme } = useTheme();
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);

  useEffect(() => {
    const handleResize = () => {
      const mobileStatus = window.innerWidth <= 768;
      setIsMobile(mobileStatus);
      if (!mobileStatus) {
        setIsMobileMenuOpen(false);
      }
    };
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return (
    <div className="page" style={{ display: 'flex', minHeight: '100vh', flexDirection: 'column' }}>
      {/* Top Header */}
      <header className="header">
        <div className="brand-wrap" style={{ maxWidth: '100%', padding: '0.8rem 1.5rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div className="brand-left">
            <div className="brand-icon" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: 28, height: 28, overflow: 'hidden', borderRadius: '4px', background: 'rgba(255,255,255,0.03)', border: '1px solid var(--border-soft)' }}>
              <img src="/logo.png" alt="crypt.ml logo" style={{ width: '100%', height: '100%', objectFit: 'contain' }} />
            </div>
            <div>
              <h1 style={{ fontSize: '1.1rem', fontWeight: 800, letterSpacing: '-0.02em', color: 'var(--text-primary)', lineHeight: 1.2 }}>
                crypt.ml
              </h1>
              {!isMobile && (
                <p style={{ margin: 0, fontSize: '0.68rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
                  Enterprise Multi-Agent Compliance System
                </p>
              )}
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: isMobile ? '0.75rem' : '1.5rem' }}>
            {/* Server Status Badge (Hidden or shrunk on small screens) */}
            <div style={{ 
              display: 'flex', 
              alignItems: 'center', 
              gap: '0.4rem', 
              fontSize: '0.72rem', 
              background: 'rgba(16, 185, 129, 0.08)', 
              color: '#10b981', 
              border: '1px solid rgba(16, 185, 129, 0.2)', 
              padding: '0.2rem 0.6rem', 
              borderRadius: '999px', 
              fontWeight: 700 
            }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block' }}></span>
              {isMobile ? 'API Active' : 'Backend API Active'}
            </div>

            {/* Theme Toggle */}
            <div className="theme-toggle-wrap">
              {!isMobile && <span className="theme-label" style={{ marginRight: '0.3rem' }}>{theme === 'dark' ? 'Dark' : 'Light'}</span>}
              <button 
                onClick={toggleTheme} 
                style={{ 
                  background: 'none', 
                  border: 'none', 
                  color: 'var(--text-primary)', 
                  cursor: 'pointer', 
                  display: 'flex', 
                  alignItems: 'center', 
                  padding: 4 
                }}
                aria-label="Toggle Theme"
              >
                {theme === 'dark' ? <Sun size={18} className="text-yellow-400" /> : <Moon size={18} />}
              </button>
            </div>

            {/* Hamburger Button (Mobile Only) */}
            {isMobile && (
              <button 
                onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} 
                style={{ 
                  background: 'none', 
                  border: 'none', 
                  color: 'var(--text-primary)', 
                  cursor: 'pointer', 
                  display: 'flex', 
                  alignItems: 'center', 
                  padding: 4 
                }}
                aria-label="Toggle Navigation Menu"
              >
                {isMobileMenuOpen ? <X size={22} /> : <Menu size={22} />}
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main Layout Grid */}
      <div style={{ display: 'flex', flex: 1, position: 'relative' }}>
        {/* Backdrop for mobile drawer */}
        {isMobile && (
          <div 
            className={`mobile-sidebar-backdrop ${isMobileMenuOpen ? 'active' : ''}`}
            onClick={() => setIsMobileMenuOpen(false)}
          />
        )}

        {/* Navigation Sidebar */}
        <aside 
          className={isMobile ? `mobile-sidebar-drawer ${isMobileMenuOpen ? 'open' : ''}` : ''}
          style={isMobile ? {
            padding: '1.5rem 1rem',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between',
            height: '100%'
          } : {
            width: '240px', 
            borderRight: '1px solid var(--border-soft)', 
            background: 'var(--card-bg-alt)',
            padding: '1.5rem 1rem',
            display: 'flex',
            flexDirection: 'column',
            justifyContent: 'space-between'
          }}
        >
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.68rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '0.05em', paddingLeft: '0.6rem', marginBottom: '0.5rem' }}>
              Core Operations
            </span>
            <NavLink 
              to="/" 
              end
              onClick={() => setIsMobileMenuOpen(false)}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.65rem 0.8rem',
                borderRadius: '8px',
                color: isActive ? '#3b82f6' : 'var(--text-primary)',
                background: isActive ? 'rgba(59, 130, 246, 0.08)' : 'transparent',
                fontWeight: isActive ? 700 : 500,
                textDecoration: 'none',
                fontSize: '0.85rem',
                border: isActive ? '1px solid rgba(59, 130, 246, 0.15)' : '1px solid transparent'
              })}
            >
              <LayoutDashboard size={16} />
              Overview
            </NavLink>

            <NavLink 
              to="/agents" 
              onClick={() => setIsMobileMenuOpen(false)}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.65rem 0.8rem',
                borderRadius: '8px',
                color: isActive ? '#3b82f6' : 'var(--text-primary)',
                background: isActive ? 'rgba(59, 130, 246, 0.08)' : 'transparent',
                fontWeight: isActive ? 700 : 500,
                textDecoration: 'none',
                fontSize: '0.85rem',
                border: isActive ? '1px solid rgba(59, 130, 246, 0.15)' : '1px solid transparent'
              })}
            >
              <Cpu size={16} />
              Agent Dashboard
              {!isMobile && (
                <span style={{ 
                  fontSize: '0.6rem', 
                  background: 'rgba(59, 130, 246, 0.12)', 
                  color: '#3b82f6', 
                  padding: '0.05rem 0.35rem', 
                  borderRadius: '4px',
                  marginLeft: 'auto',
                  fontWeight: 800
                }}>
                  CLEARING
                </span>
              )}
            </NavLink>

            <NavLink 
              to="/analysis" 
              onClick={() => setIsMobileMenuOpen(false)}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.65rem 0.8rem',
                borderRadius: '8px',
                color: isActive ? '#3b82f6' : 'var(--text-primary)',
                background: isActive ? 'rgba(59, 130, 246, 0.08)' : 'transparent',
                fontWeight: isActive ? 700 : 500,
                textDecoration: 'none',
                fontSize: '0.85rem',
                border: isActive ? '1px solid rgba(59, 130, 246, 0.15)' : '1px solid transparent'
              })}
            >
              <Table size={16} />
              Transactions & Cases
            </NavLink>

            <span style={{ fontSize: '0.68rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '0.05em', paddingLeft: '0.6rem', marginTop: '1.5rem', marginBottom: '0.5rem' }}>
              Configuration
            </span>

            <NavLink 
              to="/rules" 
              onClick={() => setIsMobileMenuOpen(false)}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.65rem 0.8rem',
                borderRadius: '8px',
                color: isActive ? '#3b82f6' : 'var(--text-primary)',
                background: isActive ? 'rgba(59, 130, 246, 0.08)' : 'transparent',
                fontWeight: isActive ? 700 : 500,
                textDecoration: 'none',
                fontSize: '0.85rem',
                border: isActive ? '1px solid rgba(59, 130, 246, 0.15)' : '1px solid transparent'
              })}
            >
              <FileText size={16} />
              Compliance Rules
            </NavLink>

            <NavLink 
              to="/assistant" 
              onClick={() => setIsMobileMenuOpen(false)}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.65rem 0.8rem',
                borderRadius: '8px',
                color: isActive ? '#3b82f6' : 'var(--text-primary)',
                background: isActive ? 'rgba(59, 130, 246, 0.08)' : 'transparent',
                fontWeight: isActive ? 700 : 500,
                textDecoration: 'none',
                fontSize: '0.85rem',
                border: isActive ? '1px solid rgba(59, 130, 246, 0.15)' : '1px solid transparent'
              })}
            >
              <MessageSquare size={16} />
              AI AML Assistant
            </NavLink>

            <NavLink 
              to="/model-studio" 
              onClick={() => setIsMobileMenuOpen(false)}
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.65rem 0.8rem',
                borderRadius: '8px',
                color: isActive ? '#3b82f6' : 'var(--text-primary)',
                background: isActive ? 'rgba(59, 130, 246, 0.08)' : 'transparent',
                fontWeight: isActive ? 700 : 500,
                textDecoration: 'none',
                fontSize: '0.85rem',
                border: isActive ? '1px solid rgba(59, 130, 246, 0.15)' : '1px solid transparent'
              })}
            >
              <Binary size={16} />
              Model Studio
            </NavLink>
          </div>

          {/* Sidebar Footer Info */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', borderTop: '1px solid var(--border-soft)', paddingTop: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
              <Activity size={12} color="#3b82f6" />
              <span>Agents Active: 5</span>
            </div>
            <div style={{ fontSize: '0.62rem', color: 'var(--text-secondary)', opacity: 0.8 }}>
              v1.2.0 • Production Demo
            </div>
          </div>
        </aside>

        {/* Content Panel */}
        <main style={{ flex: 1, padding: isMobile ? '1rem' : '2rem', overflowY: 'auto', background: 'var(--bg-main)', minWidth: 0 }}>
          {children}
        </main>
      </div>
    </div>
  );
}
