"""Git Module — Multi-repo git workflow.

Wraps the real `git` binary via subprocess. `/git repo <path>` sets which
repo subsequent commands target (default: the backend process's working
directory, which is usually NOT the same as your shell's cwd — always check
with `/git repo` first). Read commands (status/log/diff/branch/remote) run
freely; commands that can discard work (reset-hard, clean, checkout that
would lose changes) ask for confirmation first, same as the real git CLI's
own safety net plus one more layer.

Commands (~16):
  /git repo [path]              Show or set the active repo path
  /git status                     git status --short
  /git log [n]                      Last n commits (default 10), one line each
  /git diff [path]                    Unstaged diff, optionally for one path
  /git diff-staged                      Staged diff
  /git branch                             List branches (current marked)
  /git current-branch                       Just the current branch name
  /git remote                                 List remotes
  /git add <path>                               Stage a path
  /git commit <message>                           Commit staged changes
  /git pull                                         git pull
  /git push                                           git push
  /git fetch                                            git fetch
  /git stash                                              git stash
  /git stash-pop                                            git stash pop
  /git reset-hard                                             Discard ALL changes (confirms)
  /git explain                                                  How this module works
"""

import os
import subprocess
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


class GitModule(Module):
    name = "git"
    version = "1.0.0"
    description = "Multi-repo git workflow + GitHub CLI integration"
    author = "termaid"

    def on_load(self):
        for cmd in ["repo", "status", "log", "diff", "diff-staged", "branch",
                    "current-branch", "remote", "add", "commit", "pull", "push",
                    "fetch", "stash", "stash-pop", "reset-hard", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))
        self._repo = os.getcwd()

    def _run(self, args: list[str], timeout: int = 20) -> tuple[bool, str]:
        try:
            r = subprocess.run(["git", "-C", self._repo] + args, capture_output=True,
                              text=True, timeout=timeout, encoding="utf-8", errors="replace")
        except FileNotFoundError:
            return False, "git is not installed or not on PATH"
        except subprocess.TimeoutExpired:
            return False, "git command timed out"
        if r.returncode != 0:
            return False, (r.stderr or r.stdout).strip()
        return True, r.stdout.strip()

    @safe
    def cmd_repo(self, arg=""):
        """Show or set the active repo path"""
        path = (arg or "").strip()
        if not path:
            return f"[git] Active repo: {self._repo}"
        p = Path(path).expanduser().resolve()
        if not p.is_dir():
            return f"[git] Not a directory: {p}"
        self._repo = str(p)
        ok, out = self._run(["rev-parse", "--is-inside-work-tree"])
        note = "" if (ok and out == "true") else "  (warning: doesn't look like a git repo)"
        return f"[git] Active repo set to {self._repo}{note}"

    @safe
    def cmd_status(self, arg=""):
        """git status --short"""
        ok, out = self._run(["status", "--short", "--branch"])
        if not ok:
            return f"[git] {out}"
        return f"[git] Status ({self._repo}):\n{out}" if out.strip() else f"[git] Clean ({self._repo})"

    @safe
    def cmd_log(self, arg=""):
        """Last n commits (default 10), one line each"""
        try:
            n = int((arg or "10").strip())
        except Exception:
            n = 10
        ok, out = self._run(["log", f"-{max(1, min(n, 200))}", "--oneline"])
        if not ok:
            return f"[git] {out}"
        return out or "[git] No commits yet."

    @safe
    def cmd_diff(self, arg=""):
        """Unstaged diff, optionally for one path"""
        args = ["diff"]
        if arg.strip():
            args.extend(["--", arg.strip()])
        ok, out = self._run(args)
        if not ok:
            return f"[git] {out}"
        return out or "[git] No unstaged changes."

    @safe
    def cmd_diff_staged(self, arg=""):
        """Staged diff"""
        ok, out = self._run(["diff", "--staged"])
        if not ok:
            return f"[git] {out}"
        return out or "[git] Nothing staged."

    @safe
    def cmd_branch(self, arg=""):
        """List branches (current marked)"""
        ok, out = self._run(["branch", "--list"])
        if not ok:
            return f"[git] {out}"
        return out or "[git] No branches found."

    @safe
    def cmd_current_branch(self, arg=""):
        """Just the current branch name"""
        ok, out = self._run(["branch", "--show-current"])
        if not ok:
            return f"[git] {out}"
        return out or "[git] (detached HEAD)"

    @safe
    def cmd_remote(self, arg=""):
        """List remotes"""
        ok, out = self._run(["remote", "-v"])
        if not ok:
            return f"[git] {out}"
        return out or "[git] No remotes configured."

    @safe
    def cmd_add(self, arg=""):
        """Stage a path"""
        path = (arg or "").strip()
        if not path:
            return "[git] Usage: /git add <path>"
        ok, out = self._run(["add", path])
        return f"[git] Staged {path}" if ok else f"[git] {out}"

    @safe
    def cmd_commit(self, arg=""):
        """Commit staged changes"""
        message = (arg or "").strip()
        if not message:
            return "[git] Usage: /git commit <message>"
        ok, out = self._run(["commit", "-m", message])
        return out if ok else f"[git] {out}"

    @safe
    def cmd_pull(self, arg=""):
        """git pull"""
        ok, out = self._run(["pull"], timeout=60)
        return out if ok else f"[git] {out}"

    @safe
    def cmd_push(self, arg=""):
        """git push"""
        ok, out = self._run(["push"], timeout=60)
        return out if ok else f"[git] {out}"

    @safe
    def cmd_fetch(self, arg=""):
        """git fetch"""
        ok, out = self._run(["fetch"], timeout=60)
        return out or "[git] Fetched (no output)" if ok else f"[git] {out}"

    @safe
    def cmd_stash(self, arg=""):
        """git stash"""
        ok, out = self._run(["stash"])
        return out if ok else f"[git] {out}"

    @safe
    def cmd_stash_pop(self, arg=""):
        """git stash pop"""
        ok, out = self._run(["stash", "pop"])
        return out if ok else f"[git] {out}"

    @safe
    def cmd_reset_hard(self, arg=""):
        """Discard ALL uncommitted changes (confirms — this is genuinely destructive)"""
        if (arg or "").strip().lower() != "confirm":
            return (f"[git] This discards ALL uncommitted changes in {self._repo} — cannot be undone. "
                    f"Re-run as: /git reset-hard confirm")
        ok, out = self._run(["reset", "--hard"])
        return out if ok else f"[git] {out}"

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
