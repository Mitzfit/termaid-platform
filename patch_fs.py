import os

# 1. Patch Backend (main.py)
main_py_path = "backend/main.py"
with open(main_py_path, "r") as f: main_content = f.read()

if "/api/fs" not in main_content:
    api_endpoint = """
@app.get("/api/fs")
async def list_fs(path: str = "."):
    import os
    try:
        base = os.path.abspath(path)
        items = []
        if os.path.exists(base) and os.path.isdir(base):
            parent = os.path.dirname(base)
            if parent != base:
                items.append({"name": "..", "is_dir": True, "path": parent})
            for f in sorted(os.listdir(base)):
                full = os.path.join(base, f)
                items.append({"name": f, "is_dir": os.path.isdir(full), "path": full})
        return {"path": base, "items": items}
    except Exception as e:
        return {"error": str(e)}
"""
    main_content = main_content.replace('@app.get("/api/health")', api_endpoint + '\n@app.get("/api/health")')
    with open(main_py_path, "w") as f: f.write(main_content)
    print("[+] Successfully added /api/fs endpoint to backend.")

# 2. Patch Frontend HTML (index.html)
html_path = "frontend/index.html"
with open(html_path, "r") as f: html = f.read()

if "panel-fs" not in html:
    icon_patch = '<div class="icon-btn" data-target="panel-fs" title="File Explorer">📁</div>\n        <div class="icon-btn" data-target="panel-mermaid"'
    if 'data-target="panel-mermaid"' in html:
        html = html.replace('<div class="icon-btn" data-target="panel-mermaid"', icon_patch)
    else:
        icon_patch2 = '<div class="icon-btn" data-target="panel-fs" title="File Explorer">📁</div>\n        <div class="icon-btn" data-target="panel-help"'
        html = html.replace('<div class="icon-btn" data-target="panel-help"', icon_patch2)

if 'id="panel-fs"' not in html:
    panel_patch = """
          <!-- FILE SYSTEM EXPLORER -->
          <div id="panel-fs" class="panel-view hidden">
            <div class="section-block">
              <h4>File Explorer</h4>
              <div class="config-group">
                <input type="text" id="fs-path-input" value="." style="width: 100%; padding: 8px; background: #0d1117; color: #79c0ff; border: 1px solid #30363d; border-radius: 4px; font-family: 'JetBrains Mono', monospace; font-size: 11px; outline: none; margin-bottom: 8px;" placeholder="Path (e.g., . or /)">
                <button id="fs-load-btn" class="btn-secondary">Load Directory</button>
              </div>
              <ul id="fs-list" class="action-list" style="margin-top: 10px; max-height: 50vh; overflow-y: auto;">
                <li><span class="sub-text">Ready to browse.</span></li>
              </ul>
            </div>
          </div>
          <!-- 7. HELP -->
"""
    html = html.replace('<!-- 7. HELP -->', panel_patch)
    with open(html_path, "w") as f: f.write(html)
    print("[+] Successfully injected File Explorer HTML components.")

# 3. Patch Frontend TS (main.ts)
ts_path = "frontend/src/main.ts"
with open(ts_path, "r") as f: ts_content = f.read()

if "fs-path-input" not in ts_content:
    with open(ts_path, "a") as f:
        f.write("""
// --- FILE SYSTEM EXPLORER LOGIC ---
setTimeout(() => {
  const fsIcon = document.querySelector('[data-target="panel-fs"]');
  const fsPathInput = document.getElementById('fs-path-input') as HTMLInputElement;
  const fsLoadBtn = document.getElementById('fs-load-btn');
  const fsList = document.getElementById('fs-list');
  const terminalInput = document.getElementById('cmd') as HTMLInputElement;

  const loadFs = async (targetPath: string) => {
    if (!fsList) return;
    fsList.innerHTML = '<li><span class="sub-text">Loading...</span></li>';
    try {
      const res = await fetch(`http://localhost:8000/api/fs?path=${encodeURIComponent(targetPath)}`);
      const data = await res.json();
      
      if (data.error) {
        fsList.innerHTML = `<li><span style="color:#ff5f56; font-size: 11px;">Error: ${data.error}</span></li>`;
        return;
      }
      
      if (fsPathInput) fsPathInput.value = data.path;
      fsList.innerHTML = '';
      
      (data.items || []).forEach((item: any) => {
        const li = document.createElement('li');
        li.style.display = 'flex';
        li.style.alignItems = 'center';
        li.style.gap = '8px';
        li.style.padding = '6px 8px';
        
        const icon = item.is_dir ? '📁' : '📄';
        const color = item.is_dir ? '#79c0ff' : '#a9b1d6';
        
        li.innerHTML = `<span>${icon}</span><code style="background:transparent; border:none; padding:0; font-size:11px; color:${color}; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;" title="${item.name}">${item.name}</code>`;
        
        li.onclick = () => {
          if (item.is_dir) {
            loadFs(item.path);
          } else if (terminalInput) {
            terminalInput.value = `cat "${item.path}"`;
            terminalInput.focus();
          }
        };
        fsList.appendChild(li);
      });
    } catch (e) {
      fsList.innerHTML = '<li><span style="color:#ff5f56; font-size: 11px;">Connection Failed</span></li>';
    }
  };

  if (fsIcon) {
    fsIcon.addEventListener('click', () => {
      if (fsPathInput) loadFs(fsPathInput.value);
    });
  }
  
  if (fsLoadBtn && fsPathInput) {
    fsLoadBtn.addEventListener('click', () => loadFs(fsPathInput.value));
    fsPathInput.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') loadFs(fsPathInput.value);
    });
  }
}, 1800);
""")
    print("[+] Successfully wired File Explorer JavaScript logic.")
