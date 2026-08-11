import subprocess
import platform
import os

def run_native_command(command: str) -> str:
    """Executes a command natively on the host OS (Termux, Windows, Mac, Linux)."""
    command = command.strip()
    if not command: return ""

    # Intercept built-in commands
    if command == "help":
        return "TermAId Native Shell [Active]\nAvailable built-ins: clear, help, status\nAll other commands are routed directly to your host OS."
    if command == "status":
        return f"System: {platform.system()} {platform.release()}\nNode: {platform.node()}\nArchitecture: {platform.machine()}\nCWD: {os.getcwd()}"

    try:
        # Run natively using the actual OS shell
        result = subprocess.run(
            command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=30
        )
        output = result.stdout.strip()
        if not output: return f"[{result.returncode}] (Command executed successfully with no output)"
        return output
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 30 seconds."
    except Exception as e:
        return f"Native Shell Error: {str(e)}"
