with open('frontend/src/main.ts', 'r') as f:
    content = f.read()

# Inject an automatic "Enter" command (\r) when the websocket opens
old_ws_open = """    ws.onopen = () => {
        term?.writeln('\\x1b[36m[+] TermAId Pro PTY Engine Connected...\\x1b[0m\\r\\n');
    };"""

new_ws_open = """    ws.onopen = () => {
        term?.writeln('\\x1b[36m[+] TermAId Pro PTY Engine Connected...\\x1b[0m\\r\\n');
        // Force the shell to print its prompt immediately
        ws?.send('\\r');
    };"""

if old_ws_open in content:
    content = content.replace(old_ws_open, new_ws_open)

with open('frontend/src/main.ts', 'w') as f:
    f.write(content)
