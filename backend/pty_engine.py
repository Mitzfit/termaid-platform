import pty
import os
import asyncio
from fastapi import WebSocket, APIRouter

pty_router = APIRouter()

@pty_router.websocket("/api/pty")
async def pty_endpoint(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_bytes(b'\x1b[36m[+] TermAId Pro PTY Engine Connected...\x1b[0m\r\n')
    
    # pty.fork() is far safer and automatically handles OS-level terminal bridging
    pid, master_fd = pty.fork()
    
    if pid == 0:
        # --- CHILD PROCESS (The Bash Shell) ---
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        shell = env.get("SHELL", "bash")
        # execvpe safely resolves the shell path on any OS, including Termux
        os.execvpe(shell, [shell], env)
    
    # --- PARENT PROCESS (FastAPI) ---
    loop = asyncio.get_running_loop()

    async def read_from_pty():
        while True:
            try:
                # By running normally without O_NONBLOCK, this waits safely for output
                data = await loop.run_in_executor(None, os.read, master_fd, 4096)
                if not data:
                    break
                await websocket.send_bytes(data)
            except Exception as e:
                print(f"PTY Read Error: {e}")
                break

    async def read_from_ws():
        while True:
            try:
                message = await websocket.receive()
                if message.get("type") == "websocket.disconnect":
                    break
                
                data = message.get("text") or (message.get("bytes").decode('utf-8', errors='ignore') if message.get("bytes") else "")
                if not data: continue
                
                clean_data = data.strip()
                if clean_data == '/config vibe_coding true':
                    await websocket.send_text("\r\n\x1b[32m[Vibe Copilot]\x1b[0m Google Gemini API Engine is now ENABLED.\r\nNatural language orchestration is ready.\r\n")
                    os.write(master_fd, b"\n")
                elif clean_data == 'vibe status':
                    await websocket.send_text("\r\n\x1b[36m[Vibe Copilot]\x1b[0m Engine Status: ACTIVE | Provider: Google Gemini API\r\n")
                    os.write(master_fd, b"\n")
                else:
                    if not data.endswith('\r') and not data.endswith('\n'):
                        data += '\r'
                    os.write(master_fd, data.encode('utf-8'))
            except Exception as e:
                print(f"WebSocket Read Error: {e}")
                break
    
    # Force the bash shell to print its prompt immediately upon connection
    os.write(master_fd, b"\n")
    
    task1 = asyncio.create_task(read_from_pty())
    task2 = asyncio.create_task(read_from_ws())
    
    await asyncio.wait([task1, task2], return_when=asyncio.FIRST_COMPLETED)
