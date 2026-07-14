"""Welcome Module — Login flow orchestrator: banner + dashboard + suggestions.

Combines /banner's wordmark+quote and /header's dashboard into one login
screen, plus a few suggested first commands. Modules can freely import each
other's classes directly (they're just Python classes in the same package)
and run them standalone — that's what this does, rather than duplicating
banner/header's logic.

Commands (~5):
  /welcome show          Full login screen: banner + dashboard + suggestions
  /welcome suggestions      Just the suggested first commands
  /welcome explain            How this module works
"""

from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_SUGGESTIONS = [
    "catalog.modules              — see everything installed",
    "brain.think <message>        — talk to the AI (needs AI_PROVIDER configured)",
    "smart.suggest <mod.cmd>      — fix a typo in a command name",
    "assistant.quickstart         — a short guide to get oriented",
]


class WelcomeModule(Module):
    name = "welcome"
    version = "1.0.0"
    description = "Login flow orchestrator: banner + dashboard + suggestions"
    author = "termaid"

    def on_load(self):
        for cmd in ["show", "suggestions", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    def _run_standalone(self, module_name: str, method_name: str) -> str:
        """Import another module's class, instantiate it fresh, call one method.
        Standalone instances get no AI and aren't registered anywhere — safe
        for read-only helpers like banner/header."""
        try:
            import importlib
            mod = importlib.import_module(f"modules.{module_name}")
            cls = getattr(mod, f"{module_name.capitalize()}Module", None)
            if cls is None:
                import inspect
                for _, obj in inspect.getmembers(mod, inspect.isclass):
                    if obj.__module__ == mod.__name__ and hasattr(obj, method_name):
                        cls = obj
                        break
            if cls is None:
                return f"[welcome] ({module_name} unavailable)"
            instance = cls()
            instance.on_load()
            return getattr(instance, method_name)("")
        except Exception as e:
            return f"[welcome] ({module_name} unavailable: {e})"

    @safe
    def cmd_show(self, arg=""):
        """Full login screen: banner + dashboard + suggestions"""
        parts = [
            self._run_standalone("banner", "cmd_show"),
            "",
            self._run_standalone("header", "cmd_show"),
            "",
            "Try next:",
        ]
        parts += [f"  {s}" for s in _SUGGESTIONS]
        return "\n".join(parts)

    @safe
    def cmd_suggestions(self, arg=""):
        """Just the suggested first commands"""
        return "[welcome] Suggested next steps:\n" + "\n".join(f"  {s}" for s in _SUGGESTIONS)

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
