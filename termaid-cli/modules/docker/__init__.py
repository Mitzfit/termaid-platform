"""Docker Module — Container management: ps, run, logs, compose, prune, lint.

Wraps the real `docker` binary via subprocess. Read commands (ps/images/logs/
inspect) run freely; stop/start/restart are reversible so they run directly;
remove and prune are gated behind confirmation since they permanently delete
containers/images/volumes.

Commands (~15):
  /docker ps [--all]           List containers (running, or all with --all)
  /docker images                 List images
  /docker logs <container> [n]     Last n log lines (default 100)
  /docker inspect <container>        Full inspect JSON (truncated)
  /docker stop <container>             Stop a running container
  /docker start <container>              Start a stopped container
  /docker restart <container>              Restart a container
  /docker remove <container>                 Remove a container (confirms)
  /docker prune                                Remove all stopped containers + dangling images (confirms)
  /docker compose-ps                             docker compose ps (in the active repo, see /git repo)
  /docker explain                                  How this module works
"""

import subprocess
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class DockerModule(Module):
    name = "docker"
    version = "1.0.0"
    description = "Container management: ps, run, logs, compose, prune, lint"
    author = "termaid"

    def on_load(self):
        for cmd in ["ps", "images", "logs", "inspect", "stop", "start",
                    "restart", "remove", "prune", "compose-ps", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

    def _run(self, args: list[str], timeout: int = 20) -> tuple[bool, str]:
        try:
            r = subprocess.run(["docker"] + args, capture_output=True, text=True,
                              timeout=timeout, encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return False, "docker is not installed or not on PATH"
        except subprocess.TimeoutExpired:
            return False, "docker command timed out"
        if r.returncode != 0:
            return False, (r.stderr or r.stdout).strip()
        return True, r.stdout.strip()

    @safe
    def cmd_ps(self, arg=""):
        """List containers (running, or all with --all)"""
        args = ["ps", "--format", "table {{.Names}}\\t{{.Status}}\\t{{.Image}}\\t{{.Ports}}"]
        if (arg or "").strip() == "--all":
            args.insert(1, "-a")
        ok, out = self._run(args)
        if not ok:
            return f"[docker] {out}"
        return out or "[docker] No containers."

    @safe
    def cmd_images(self, arg=""):
        """List images"""
        ok, out = self._run(["images", "--format", "table {{.Repository}}\\t{{.Tag}}\\t{{.Size}}"])
        if not ok:
            return f"[docker] {out}"
        return out or "[docker] No images."

    @safe
    def cmd_logs(self, arg=""):
        """Last n log lines (default 100): /docker logs <container> [n]"""
        parts = (arg or "").split()
        if not parts:
            return "[docker] Usage: /docker logs <container> [n]"
        name = parts[0]
        n = parts[1] if len(parts) > 1 else "100"
        ok, out = self._run(["logs", "--tail", n, name])
        if not ok:
            return f"[docker] {out}"
        return out or "[docker] (no log output)"

    @safe
    def cmd_inspect(self, arg=""):
        """Full inspect JSON (truncated)"""
        name = (arg or "").strip()
        if not name:
            return "[docker] Usage: /docker inspect <container>"
        ok, out = self._run(["inspect", name])
        if not ok:
            return f"[docker] {out}"
        return out[:4000] + ("\n... (truncated)" if len(out) > 4000 else "")

    @safe
    def cmd_stop(self, arg=""):
        """Stop a running container"""
        name = (arg or "").strip()
        if not name:
            return "[docker] Usage: /docker stop <container>"
        ok, out = self._run(["stop", name])
        return f"[docker] Stopped {out}" if ok else f"[docker] {out}"

    @safe
    def cmd_start(self, arg=""):
        """Start a stopped container"""
        name = (arg or "").strip()
        if not name:
            return "[docker] Usage: /docker start <container>"
        ok, out = self._run(["start", name])
        return f"[docker] Started {out}" if ok else f"[docker] {out}"

    @safe
    def cmd_restart(self, arg=""):
        """Restart a container"""
        name = (arg or "").strip()
        if not name:
            return "[docker] Usage: /docker restart <container>"
        ok, out = self._run(["restart", name])
        return f"[docker] Restarted {out}" if ok else f"[docker] {out}"

    @safe
    def cmd_remove(self, arg=""):
        """Remove a container (confirms — this is permanent): /docker remove <container> confirm"""
        parts = (arg or "").split()
        if not parts:
            return "[docker] Usage: /docker remove <container>"
        name = parts[0]
        if len(parts) < 2 or parts[1].lower() != "confirm":
            return f"[docker] Removing '{name}' is permanent. Re-run as: /docker remove {name} confirm"
        ok, out = self._run(["rm", "-f", name])
        return f"[docker] Removed {out}" if ok else f"[docker] {out}"

    @safe
    def cmd_prune(self, arg=""):
        """Remove all stopped containers + dangling images (confirms — this is permanent)"""
        if (arg or "").strip().lower() != "confirm":
            return "[docker] This permanently removes ALL stopped containers + dangling images. Re-run as: /docker prune confirm"
        ok1, out1 = self._run(["container", "prune", "-f"])
        ok2, out2 = self._run(["image", "prune", "-f"])
        return f"[docker] Containers: {out1}\n[docker] Images: {out2}"

    @safe
    def cmd_compose_ps(self, arg=""):
        """docker compose ps (in the current directory)"""
        ok, out = self._run(["compose", "ps"])
        if not ok:
            return f"[docker] {out}"
        return out or "[docker] No compose services running here."

    @safe
    def cmd_explain(self, arg=""):
        """How this module works"""
        try:
            from _shared.explain import auto_explain
            return auto_explain(self)
        except ImportError:
            cmds = sorted(self._commands.keys()) if hasattr(self, "_commands") else []
            lines = [f"[{self.name}] {self.description}", "", "Commands:"]
            for c in cmds:
                lines.append(f"  /{self.name} {c}")
            return "\n".join(lines)
