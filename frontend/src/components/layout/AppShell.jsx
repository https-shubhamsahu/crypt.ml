import React from 'react';
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
  Activity
} from 'lucide-react';

export default function AppShell({ children }) {
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="page" style={{ display: 'flex', minHeight: '100vh', flexDirection: 'column' }}>
      {/* Top Header */}
      <header className="header">
        <div className="brand-wrap" style={{ maxWidth: '100%', padding: '0.8rem 1.5rem' }}>
          <div className="brand-left">
            <div className="brand-icon" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Shield size={20} color="#3b82f6" />
            </div>
            <div>
              <h1 style={{ fontSize: '1.25rem', fontWeight: 800, background: 'linear-gradient(90deg, #3b82f6, #9333ea)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
                AEGIS-AML
              </h1>
              <p style={{ margin: 0, fontSize: '0.68rem', color: 'var(--text-secondary)', fontWeight: 600 }}>
                Enterprise Multi-Agent Compliance System
              </p>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
            {/* Server Status Badge */}
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.72rem', background: 'rgba(16, 185, 129, 0.08)', color: '#10b981', border: '1px solid rgba(16, 185, 129, 0.2)', padding: '0.2rem 0.6rem', borderRadius: '999px', fontWeight: 700 }}>
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#10b981', display: 'inline-block' }}></span>
              Backend API Active
            </div>

            {/* Theme Toggle */}
            <div className="theme-toggle-wrap">
              <span className="theme-label">{theme === 'dark' ? 'Dark' : 'Light'}</span>
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
              >
                {theme === 'dark' ? <Sun size={18} className="text-yellow-400" /> : <Moon size={18} />}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Layout Grid */}
      <div style={{ display: 'flex', flex: 1 }}>
        {/* Navigation Sidebar */}
        <aside style={{ 
          width: '240px', 
          borderRight: '1px solid var(--border-soft)', 
          background: 'var(--card-bg-alt)',
          padding: '1.5rem 1rem',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'space-between'
        }}>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            <span style={{ fontSize: '0.68rem', fontWeight: 800, textTransform: 'uppercase', color: 'var(--text-secondary)', letterSpacing: '0.05em', paddingLeft: '0.6rem', marginBottom: '0.5rem' }}>
              Core Operations
            </span>
            <NavLink 
              to="/" 
              end
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
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '0.75rem',
                padding: '0.65rem 0.8rem',
                borderRadius: '8px',
                color: isActive ? '#9333ea' : 'var(--text-primary)',
                background: isActive ? 'rgba(147, 51, 234, 0.08)' : 'transparent',
                fontWeight: isActive ? 700 : 500,
                textDecoration: 'none',
                fontSize: '0.85rem',
                border: isActive ? '1px solid rgba(147, 51, 234, 0.15)' : '1px solid transparent'
              })}
            >
              <Cpu size={16} />
              Agent Dashboard
              <span style={{ 
                fontSize: '0.6rem', 
                background: 'rgba(147, 51, 234, 0.15)', 
                color: '#c084fc', 
                padding: '0.05rem 0.35rem', 
                borderRadius: '4px',
                marginLeft: 'auto',
                fontWeight: 800
              }}>
                REALTIME
              </span>
            </NavLink>

            <NavLink 
              to="/analysis" 
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
              <Activity size={12} color="#9333ea" />
              <span>Agents Active: 5</span>
            </div>
            <div style={{ fontSize: '0.62rem', color: 'var(--text-secondary)', opacity: 0.8 }}>
              v1.2.0 • Production Demo
            </div>
          </div>
        </aside>

        {/* Content Panel */}
        <main style={{ flex: 1, padding: '2rem', overflowY: 'auto', background: 'var(--bg-main)' }}>
          {children}
        </main>
      </div>
    </div>
  );
}
