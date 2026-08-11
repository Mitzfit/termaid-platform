export function initUI() {
  const icons = document.querySelectorAll('.icon-btn');
  const pages = document.querySelectorAll('.app-page');
  const terminalInput = document.getElementById('cmd') as HTMLInputElement;

  // Global Click Listener for Menu Navigation and Macros
  document.addEventListener('click', async (e) => {
    const target = e.target as HTMLElement;

    // A. Handle Navigation Menu Clicks
    const iconBtn = target.closest('.icon-btn');
    if (iconBtn) {
      const targetId = iconBtn.getAttribute('data-target');
      if (!targetId) return;

      icons.forEach(i => i.classList.remove('active'));
      iconBtn.classList.add('active');

      pages.forEach(p => p.classList.add('hidden'));
      const targetPage = document.getElementById(targetId);
      if (targetPage) targetPage.classList.remove('hidden');

      if (targetId === 'page-terminal' && terminalInput) {
        terminalInput.focus();
      }

      // Dynamic Plugin Loader
      if (targetId === 'page-plugins') {
        const pList = document.getElementById('dynamic-plugins-grid');
        if (pList) {
          pList.innerHTML = '<div style="color:#8b949e; padding: 20px;">Fetching active plugins from backend...</div>';
          try {
            const res = await (await fetch('http://localhost:8000/api/plugins')).json();
            pList.innerHTML = '';
            (res.plugins || []).forEach((p: string) => {
              const card = document.createElement('div');
              card.className = 'dash-card';
              card.innerHTML = `
                <h3>🔌 ${p}</h3>
                <p>Native integration dynamically loaded from backend/plugins.</p>
                <button class="btn-secondary exec-plugin-btn" data-plugin="${p}">Execute Plugin</button>
              `;
              pList.appendChild(card);
            });
          } catch(err) { 
            pList.innerHTML = '<div style="color:#ff5f56; padding: 20px;">Backend API Offline. Cannot fetch plugins.</div>'; 
          }
        }
      }
    }

    // B. Handle Plugin Execution Buttons
    const execBtn = target.closest('.exec-plugin-btn');
    if (execBtn) {
      triggerCommand(execBtn.getAttribute('data-plugin'));
    }

    // C. Handle Macro Buttons
    const macroBtn = target.closest('.macro-btn');
    if (macroBtn) {
      triggerCommand(macroBtn.getAttribute('data-cmd'));
    }
  });

  // D. Handle Settings & Dropdowns
  document.addEventListener('change', (e) => {
    const target = e.target as HTMLElement;
    if (target.matches('.macro-select')) {
      const select = target as HTMLSelectElement;
      const prefix = select.getAttribute('data-prefix');
      if (prefix && select.value) {
        triggerCommand(`${prefix} ${select.value}`);
      }
    }
    if (target.matches('#fontSizeSelect')) {
      const select = target as HTMLSelectElement;
      const terminalOutput = document.getElementById('terminal');
      if (terminalOutput) terminalOutput.style.fontSize = select.value;
    }
  });

  // Helper to safely execute a command via macro or plugin click
  function triggerCommand(cmdString: string | null) {
    if (cmdString && terminalInput) {
      terminalInput.value = cmdString;
      document.querySelector<HTMLElement>('[data-target="page-terminal"]')?.click();
      terminalInput.focus();
      
      // Simulate typing enter by dispatching a keyboard event
      terminalInput.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true }));
    }
  }
}
