export const BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8000';

export const ENDPOINTS = {
  // Corrected based on backend/main.py
  authRegister: '/api/auth/register',
  authLogin: '/api/auth/login',
  authRefresh: '/api/auth/refresh',
  exec: '/api/exec',
  commands: '/api/commands',
  modules: '/api/modules',
  blocked: '/api/blocked',
  history: '/api/history',
  health: '/api/health',
  scan: '/api/scan',
  wsTerminal: '/ws/terminal'
};
