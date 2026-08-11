import './style.css';
import 'xterm/css/xterm.css';
import { Terminal } from 'xterm';
import { FitAddon } from '@xterm/addon-fit';
import { ApiClient, TokenStore } from './api';

const initApp = () => {
  const getEl = (id: string) => document.getElementById(id);
  const loginPanel = getEl('login') as HTMLDivElement | null;
  const appPanel = getEl('app') as HTMLDivElement | null;
  const usernameInput = getEl('username') as HTMLInputElement | null;
  const passwordInput = getEl('password') as HTMLInputElement | null;
  const loginBtn = getEl('loginBtn') as HTMLButtonElement | null;
  const authMsg = getEl('authMsg') as HTMLDivElement | null;
  const logoutBtn = getEl('logoutBtn') as HTMLButtonElement | null;
  
  const mobileForm = getEl('mobile-form') as HTMLFormElement | null;
  const mobileCmd = getEl('mobile-cmd') as HTMLInputElement | null;
  const icons = document.querySelectorAll('.icon-btn');
  const pages = document.querySelectorAll('.app-page');

  const store = new TokenStore();
  const api = new ApiClient();
  let term: Terminal | null = null;
  let ws: WebSocket | null = null;

  document.addEventListener('click', (e) => {
    const target = e.target as HTMLElement;
    const iconBtn = target.closest('.icon-btn');
    if (iconBtn) {
      const targetId = iconBtn.getAttribute('data-target');
      if (!targetId) return;
      icons.forEach(i => i.classList.remove('active'));
      iconBtn.classList.add('active');
      pages.forEach(p => p.classList.add('hidden'));
      const targetPage = getEl(targetId);
      if (targetPage) targetPage.classList.remove('hidden');
      if (targetId === 'page-terminal') term?.focus();
    }
    const macroBtn = target.closest('.macro-btn');
    if (macroBtn) {
      const cmd = macroBtn.getAttribute('data-cmd');
      if (cmd) executeMacro(cmd);
    }
  });

  function executeMacro(cmd: string) {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(cmd + '\r');
      document.querySelector<HTMLElement>('[data-target="page-terminal"]')?.click();
    }
  }

  if (mobileForm && mobileCmd) {
    mobileForm.addEventListener('submit', (e) => {
      e.preventDefault();
      if (ws && ws.readyState === WebSocket.OPEN && mobileCmd.value.trim() !== '') {
        ws.send(mobileCmd.value + '\r');
      }
      mobileCmd.value = '';
    });
  }

  function startWorkspace() {
    loginPanel?.classList.add('hidden');
    appPanel?.classList.remove('hidden');

    const termContainer = getEl('terminal');
    if (!termContainer) return;
    termContainer.innerHTML = ''; 

    term = new Terminal({
        theme: { background: 'transparent', foreground: '#e0f2fe', cursor: '#00e6e6', selectionBackground: 'rgba(0, 230, 230, 0.3)' },
        fontFamily: '"JetBrains Mono", monospace', fontSize: 14, cursorBlink: true
    });
    
    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(termContainer);
    fitAddon.fit();
    window.addEventListener('resize', () => fitAddon.fit());

    ws = new WebSocket(`ws://localhost:8000/api/pty`);
    ws.binaryType = 'arraybuffer';
    
    ws.onmessage = (evt) => {
        if (typeof evt.data === 'string') term?.write(evt.data);
        else term?.write(new Uint8Array(evt.data));
    };

    term.onData(data => {
        if (ws?.readyState === WebSocket.OPEN) ws.send(data);
    });
  }

  if (store.access) startWorkspace();
  else loginPanel?.classList.remove('hidden');

  loginBtn?.addEventListener('click', async () => {
    if (authMsg) authMsg.textContent = 'Authenticating...';
    try {
      const pair = await api.login(usernameInput?.value || '', passwordInput?.value || '');
      store.set(pair);
      startWorkspace();
    } catch (err: any) {
      if (authMsg) authMsg.textContent = err.message || 'Login failed';
    }
  });

  logoutBtn?.addEventListener('click', () => {
    store.clear();
    window.location.reload();
  });
};
initApp();
