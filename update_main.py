import re

with open('frontend/src/main.ts', 'r') as f:
    content = f.read()

# Replace the old keydown listener with a robust form submit listener
old_code = """  if (mobileCmd) {
    mobileCmd.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(mobileCmd.value + '\\r');
        }
        mobileCmd.value = ''; // Clear input after sending
      }
    });
  }"""

new_code = """  const mobileForm = getEl('mobile-form') as HTMLFormElement | null;
  if (mobileForm && mobileCmd) {
    mobileForm.addEventListener('submit', (e) => {
      e.preventDefault();
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(mobileCmd.value + '\\r');
      }
      mobileCmd.value = '';
    });
  }"""

if old_code in content:
    content = content.replace(old_code, new_code)
else:
    # Fallback injection if the exact string matching fails
    content = content.replace("// --- TERMINAL & PTY ENGINE ---", new_code + "\n\n  // --- TERMINAL & PTY ENGINE ---")

with open('frontend/src/main.ts', 'w') as f:
    f.write(content)
