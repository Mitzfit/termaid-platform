"""Calc Module — Calculator, unit conversion, base conversion (safe — no eval).

Arithmetic is evaluated via a restricted AST walker (only numbers and +-*/%**
and parentheses), never Python's eval(), so a command like /calc.calc os.system
can't do anything but fail to parse.

Commands (12):
  /calc calc <expr>            Safe arithmetic expression (+ - * / % ** parens)
  /calc hex <n>                 Decimal -> hex
  /calc dec <hex>                Hex -> decimal
  /calc bin <n>                 Decimal -> binary
  /calc oct <n>                 Decimal -> octal
  /calc base <n> <from> <to>    Convert an integer between two bases (2-36)
  /calc convert <val> <from> <to>  Unit conversion (length, mass, temperature)
  /calc percent <value> <pct>   value * pct%
  /calc pow <base> <exp>        Exponentiation
  /calc sqrt <n>                 Square root
  /calc stats <n1> <n2> ...      mean / median / stdev of a number list
  /calc explain                 How this module works
"""

import ast
import math
import operator
import statistics
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn


# --- safe arithmetic evaluator (no eval/exec) -------------------------------

_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
    ast.FloorDiv: operator.floordiv,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_eval(expr: str):
    """Evaluate a numeric expression using only +-*/%** and parens.

    Walks a parsed AST and only permits Num/Constant/BinOp/UnaryOp nodes with
    operators in _BIN_OPS/_UNARY_OPS — anything else (names, calls, attribute
    access, subscripts) raises, so this can never execute arbitrary code.
    """
    node = ast.parse(expr, mode="eval").body

    def _eval(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp) and type(n.op) in _BIN_OPS:
            return _BIN_OPS[type(n.op)](_eval(n.left), _eval(n.right))
        if isinstance(n, ast.UnaryOp) and type(n.op) in _UNARY_OPS:
            return _UNARY_OPS[type(n.op)](_eval(n.operand))
        raise ValueError(f"disallowed expression element: {ast.dump(n)}")

    return _eval(node)


# --- unit conversion ---------------------------------------------------------

_LENGTH_TO_M = {
    "mm": 0.001, "cm": 0.01, "m": 1.0, "km": 1000.0,
    "in": 0.0254, "ft": 0.3048, "yd": 0.9144, "mi": 1609.344,
}
_MASS_TO_KG = {
    "mg": 1e-6, "g": 0.001, "kg": 1.0, "t": 1000.0,
    "oz": 0.0283495, "lb": 0.453592,
}


def _convert_unit(value: float, unit_from: str, unit_to: str) -> float:
    uf, ut = unit_from.lower(), unit_to.lower()
    if uf in ("c", "f", "k") and ut in ("c", "f", "k"):
        # normalize to Celsius first
        if uf == "f":
            c = (value - 32) * 5 / 9
        elif uf == "k":
            c = value - 273.15
        else:
            c = value
        if ut == "f":
            return c * 9 / 5 + 32
        if ut == "k":
            return c + 273.15
        return c
    if uf in _LENGTH_TO_M and ut in _LENGTH_TO_M:
        return value * _LENGTH_TO_M[uf] / _LENGTH_TO_M[ut]
    if uf in _MASS_TO_KG and ut in _MASS_TO_KG:
        return value * _MASS_TO_KG[uf] / _MASS_TO_KG[ut]
    raise ValueError(f"unsupported or mismatched units: {unit_from} -> {unit_to}")


class CalcModule(Module):
    name = "calc"
    version = "1.0.0"
    description = "Calculator, unit conversion, base conversion (safe — no eval)"
    author = "termaid"

    def on_load(self):
        for cmd in ["calc", "hex", "dec", "bin", "oct", "base", "convert",
                    "percent", "pow", "sqrt", "stats", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

    @safe
    def cmd_calc(self, arg=""):
        """Safe arithmetic expression"""
        expr = (arg or "").strip()
        if not expr:
            return "[calc] Usage: /calc calc <expression>  e.g. /calc calc (2+3)*4"
        try:
            result = _safe_eval(expr)
        except Exception as e:
            return f"[calc] Could not evaluate '{expr}': {e}"
        return f"[calc] {expr} = {result}"

    @safe
    def cmd_hex(self, arg=""):
        """Decimal -> hex"""
        try:
            n = int((arg or "").strip(), 0)
        except Exception:
            return "[calc] Usage: /calc hex <decimal-number>"
        return f"[calc] {n} = {hex(n)}"

    @safe
    def cmd_dec(self, arg=""):
        """Hex -> decimal"""
        s = (arg or "").strip()
        if not s:
            return "[calc] Usage: /calc dec <hex>  e.g. /calc dec ff or 0xff"
        try:
            n = int(s, 16) if not s.lower().startswith("0x") else int(s, 0)
        except Exception:
            return f"[calc] Not a valid hex value: {s}"
        return f"[calc] {s} = {n}"

    @safe
    def cmd_bin(self, arg=""):
        """Decimal -> binary"""
        try:
            n = int((arg or "").strip(), 0)
        except Exception:
            return "[calc] Usage: /calc bin <decimal-number>"
        return f"[calc] {n} = {bin(n)}"

    @safe
    def cmd_oct(self, arg=""):
        """Decimal -> octal"""
        try:
            n = int((arg or "").strip(), 0)
        except Exception:
            return "[calc] Usage: /calc oct <decimal-number>"
        return f"[calc] {n} = {oct(n)}"

    @safe
    def cmd_base(self, arg=""):
        """Convert an integer between two bases (2-36): /calc base <n> <from> <to>"""
        parts = (arg or "").split()
        if len(parts) != 3:
            return "[calc] Usage: /calc base <number> <from-base> <to-base>"
        num_s, from_b, to_b = parts
        try:
            from_base, to_base = int(from_b), int(to_b)
            value = int(num_s, from_base)
        except Exception as e:
            return f"[calc] Invalid input: {e}"
        if not (2 <= from_base <= 36 and 2 <= to_base <= 36):
            return "[calc] Bases must be between 2 and 36"
        digits = "0123456789abcdefghijklmnopqrstuvwxyz"
        if value == 0:
            out = "0"
        else:
            out = ""
            v = abs(value)
            while v:
                v, r = divmod(v, to_base)
                out = digits[r] + out
            if value < 0:
                out = "-" + out
        return f"[calc] {num_s} (base {from_base}) = {out} (base {to_base})"

    @safe
    def cmd_convert(self, arg=""):
        """Unit conversion: /calc convert <value> <from-unit> <to-unit>"""
        parts = (arg or "").split()
        if len(parts) != 3:
            return ("[calc] Usage: /calc convert <value> <from> <to>\n"
                    "  length: mm cm m km in ft yd mi\n"
                    "  mass:   mg g kg t oz lb\n"
                    "  temp:   c f k")
        try:
            value = float(parts[0])
            result = _convert_unit(value, parts[1], parts[2])
        except Exception as e:
            return f"[calc] {e}"
        return f"[calc] {parts[0]}{parts[1]} = {result:g}{parts[2]}"

    @safe
    def cmd_percent(self, arg=""):
        """value * pct%: /calc percent <value> <pct>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[calc] Usage: /calc percent <value> <percent>"
        try:
            value, pct = float(parts[0]), float(parts[1])
        except Exception:
            return "[calc] Both arguments must be numbers"
        return f"[calc] {pct}% of {value} = {value * pct / 100:g}"

    @safe
    def cmd_pow(self, arg=""):
        """Exponentiation: /calc pow <base> <exp>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[calc] Usage: /calc pow <base> <exponent>"
        try:
            base, exp = float(parts[0]), float(parts[1])
        except Exception:
            return "[calc] Both arguments must be numbers"
        return f"[calc] {base} ^ {exp} = {base ** exp:g}"

    @safe
    def cmd_sqrt(self, arg=""):
        """Square root"""
        try:
            n = float((arg or "").strip())
        except Exception:
            return "[calc] Usage: /calc sqrt <number>"
        if n < 0:
            return "[calc] Cannot take the real square root of a negative number"
        return f"[calc] sqrt({n:g}) = {math.sqrt(n):g}"

    @safe
    def cmd_stats(self, arg=""):
        """mean/median/stdev of a number list: /calc stats <n1> <n2> ..."""
        parts = (arg or "").split()
        if len(parts) < 2:
            return "[calc] Usage: /calc stats <n1> <n2> ... (at least 2 numbers)"
        try:
            nums = [float(p) for p in parts]
        except Exception:
            return "[calc] All arguments must be numbers"
        lines = [f"[calc] Stats for {len(nums)} number(s):"]
        lines.append(f"  sum:    {sum(nums):g}")
        lines.append(f"  mean:   {statistics.mean(nums):g}")
        lines.append(f"  median: {statistics.median(nums):g}")
        if len(nums) > 1:
            lines.append(f"  stdev:  {statistics.stdev(nums):g}")
        lines.append(f"  min:    {min(nums):g}")
        lines.append(f"  max:    {max(nums):g}")
        return "\n".join(lines)

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
