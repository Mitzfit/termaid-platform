import os

html_path = "frontend/index.html"
with open(html_path, "r") as f: html = f.read()

# Add Mermaid CDN to head
if "mermaid.esm.min.mjs" not in html:
    head_patch = """
  <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Inter:wght@400;500;600&display=swap" rel="stylesheet" />
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({ startOnLoad: false, theme: 'dark' });
    window.mermaid = mermaid;
  </script>
"""
    html = html.replace('<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500&family=Inter:wght@400;500;600&display=swap" rel="stylesheet" />', head_patch)

# Add Activity Bar Icon (Map Emoji)
if "panel-mermaid" not in html:
    icon_patch = '<div class="icon-btn" data-target="panel-mermaid" title="Mermaid Visualizer">🗺️</div>\n        <div class="icon-btn" data-target="panel-help"'
    html = html.replace('<div class="icon-btn" data-target="panel-help"', icon_patch)

# Add Side Panel UI
if 'id="panel-mermaid"' not in html:
    panel_patch = """
          <!-- MERMAID VISUALIZER -->
          <div id="panel-mermaid" class="panel-view hidden">
            <div class="section-block">
              <h4>Workflow Visualizer</h4>
              <p class="sub-text">Map automation logic dynamically.</p>
              <textarea id="mermaid-input" style="width: 100%; height: 180px; background: #0d1117; color: #79c0ff; border: 1px solid #30363d; border-radius: 4px; padding: 8px; font-family: 'JetBrains Mono', monospace; font-size: 11px; margin-top: 10px; resize: vertical; outline: none;">graph TD;
    A[Start Automation] --> B{Check Auth};
    B -- Valid --> C[Deploy Docker];
    B -- Invalid --> D[Halt & Alert];
    C --> E[Sync GitHub Repo];</textarea>
              <button id="renderMermaidBtn" class="btn-primary" style="margin-top: 10px; width: 100%;">Render Workflow</button>
            </div>
          </div>
          <!-- 7. HELP -->
"""
    html = html.replace('<!-- 7. HELP -->', panel_patch)

# Add Floating Render Window
if 'id="mermaid-window"' not in html:
    floating_patch = """
    <!-- Floating Mermaid Window -->
    <div id="mermaid-window" class="window-panel center-screen hidden" style="width: 60%; min-width: 400px; height: 60%; min-height: 400px; display: flex; flex-direction: column; left: 60%;">
      <div class="window-titlebar">
        <div class="window-controls"><span class="dot close" id="closeMermaidBtn" style="cursor:pointer;"></span><span class="dot min"></span><span class="dot max"></span></div>
        <div class="window-title">Workflow Visualizer Render</div>
      </div>
      <div class="window-content" style="flex: 1; overflow: auto; background: #010409; display: flex; justify-content: center; align-items: center; padding: 20px;" id="mermaid-output">
      </div>
    </div>
  </div>
  <script type="module" src="/src/main.ts"></script>
"""
    html = html.replace('</div>\n  <script type="module" src="/src/main.ts"></script>', floating_patch)
    with open(html_path, "w") as f: f.write(html)
    print("[+] Successfully injected Mermaid HTML components.")

# 2. Patch Frontend TS (main.ts)
ts_path = "frontend/src/main.ts"
with open(ts_path, "r") as f: ts_content = f.read()

# Make sure we don't duplicate the JS logic
if "MERMAID VISUALIZER LOGIC" not in ts_content:
    with open(ts_path, "a") as f:
        f.write("""
// --- MERMAID VISUALIZER LOGIC ---
setTimeout(() => {
  const renderBtn = document.getElementById('renderMermaidBtn');
  const mermaidInput = document.getElementById('mermaid-input') as HTMLTextAreaElement;
  const mermaidWindow = document.getElementById('mermaid-window');
  const mermaidOutput = document.getElementById('mermaid-output');
  const closeMermaidBtn = document.getElementById('closeMermaidBtn');

  if (renderBtn && mermaidInput && mermaidWindow && mermaidOutput) {
    renderBtn.addEventListener('click', async () => {
      try {
        mermaidWindow.classList.remove('hidden');
        mermaidOutput.innerHTML = '<span style="color:#8b949e;">Rendering engine booting...</span>';
        const code = mermaidInput.value;
        
        // @ts-ignore
        if (window.mermaid) {
          // @ts-ignore
          const { svg } = await window.mermaid.render('mermaid-graph', code);
          mermaidOutput.innerHTML = svg;
        } else {
          mermaidOutput.innerHTML = '<span style="color:#ffbd2e;">Waiting for CDN to load... Click render again.</span>';
        }
      } catch (e: any) {
        mermaidOutput.innerHTML = `<span style="color:#ff5f56; font-family: monospace; font-size: 11px;">Syntax Error: ${e.message || e}</span>`;
      }
    });
  }

  if (closeMermaidBtn && mermaidWindow) {
    closeMermaidBtn.addEventListener('click', () => {
      mermaidWindow.classList.add('hidden');
    });
  }
}, 1500);
""")
    print("[+] Successfully wired Mermaid JavaScript logic.")
