"""Paper Module — Paper trading simulator with real market data.

Simulated buy/sell against real-time crypto prices (CoinGecko, same source
/markets uses). No real money or exchange account involved — this is purely
a local ledger: a starting USD balance, buy/sell moves USD into/out of coin
positions at the fetched price, and P&L is computed against current prices.

Commands (~11):
  /paper reset [amount]        Reset to a fresh account (default $10,000 starting balance)
  /paper balance                 Cash balance
  /paper buy <coin> <usd>          Buy $<usd> worth of <coin> at current price
  /paper sell <coin> <usd>          Sell $<usd> worth of <coin> at current price
  /paper positions                    Show open positions with current value + P&L
  /paper history                        Trade log
  /paper networth                         Cash + positions at current prices
  /paper explain                            How this module works
"""

import json
import os
import sys
import time
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_API = "https://api.coingecko.com/api/v3"
_STARTING_BALANCE = 10_000.0


class PaperModule(Module):
    name = "paper"
    version = "1.0.0"
    description = "Paper trading simulator with real market data"
    author = "termaid"

    def on_load(self):
        for cmd in ["reset", "balance", "buy", "sell", "positions",
                    "history", "networth", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "paper"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "account.json"
        if not self._file.exists():
            self._save(self._fresh_account(_STARTING_BALANCE))

    def _fresh_account(self, balance: float) -> dict:
        return {"cash": balance, "positions": {}, "trades": []}

    def _load(self) -> dict:
        try:
            data = json.loads(self._file.read_text())
            data.setdefault("cash", _STARTING_BALANCE)
            data.setdefault("positions", {})
            data.setdefault("trades", [])
            return data
        except Exception:
            return self._fresh_account(_STARTING_BALANCE)

    def _save(self, data: dict) -> None:
        self._file.write_text(json.dumps(data, indent=2))

    def _price(self, coin: str) -> float | None:
        try:
            import httpx
        except ImportError:
            return None
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(f"{_API}/simple/price", params={"ids": coin, "vs_currencies": "usd"})
                r.raise_for_status()
                data = r.json()
                return data.get(coin, {}).get("usd")
        except Exception:
            return None

    @safe
    def cmd_reset(self, arg=""):
        """Reset to a fresh account"""
        try:
            amount = float((arg or str(_STARTING_BALANCE)).strip())
        except Exception:
            amount = _STARTING_BALANCE
        self._save(self._fresh_account(amount))
        return f"[paper] Account reset. Starting balance: ${amount:,.2f}"

    @safe
    def cmd_balance(self, arg=""):
        """Cash balance"""
        data = self._load()
        return f"[paper] Cash: ${data['cash']:,.2f}"

    @safe
    def cmd_buy(self, arg=""):
        """Buy $<usd> worth of <coin> at current price: /paper buy <coin> <usd-amount>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[paper] Usage: /paper buy <coin-id> <usd-amount>"
        coin, usd_s = parts[0].lower(), parts[1]
        try:
            usd = float(usd_s)
        except Exception:
            return "[paper] Amount must be a number"
        if usd <= 0:
            return "[paper] Amount must be positive"
        data = self._load()
        if usd > data["cash"]:
            return f"[paper] Insufficient cash: have ${data['cash']:,.2f}, need ${usd:,.2f}"
        price = self._price(coin)
        if price is None:
            return f"[paper] Could not fetch a price for '{coin}'"
        qty = usd / price
        data["cash"] -= usd
        data["positions"][coin] = data["positions"].get(coin, 0.0) + qty
        data["trades"].append({"side": "buy", "coin": coin, "usd": usd, "qty": qty,
                              "price": price, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
        self._save(data)
        return f"[paper] Bought {qty:g} {coin} @ ${price:,.2f} (${usd:,.2f})"

    @safe
    def cmd_sell(self, arg=""):
        """Sell $<usd> worth of <coin> at current price: /paper sell <coin> <usd-amount>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[paper] Usage: /paper sell <coin-id> <usd-amount>"
        coin, usd_s = parts[0].lower(), parts[1]
        try:
            usd = float(usd_s)
        except Exception:
            return "[paper] Amount must be a number"
        data = self._load()
        held_qty = data["positions"].get(coin, 0.0)
        if held_qty <= 0:
            return f"[paper] No position in '{coin}'"
        price = self._price(coin)
        if price is None:
            return f"[paper] Could not fetch a price for '{coin}'"
        held_value = held_qty * price
        if usd > held_value:
            usd = held_value  # sell everything if asking for more than we hold
        qty = usd / price
        data["positions"][coin] = held_qty - qty
        if data["positions"][coin] <= 1e-12:
            del data["positions"][coin]
        data["cash"] += usd
        data["trades"].append({"side": "sell", "coin": coin, "usd": usd, "qty": qty,
                              "price": price, "at": time.strftime("%Y-%m-%d %H:%M:%S")})
        self._save(data)
        return f"[paper] Sold {qty:g} {coin} @ ${price:,.2f} (${usd:,.2f})"

    @safe
    def cmd_positions(self, arg=""):
        """Show open positions with current value + P&L"""
        data = self._load()
        if not data["positions"]:
            return "[paper] No open positions."
        lines = ["[paper] Positions:"]
        for coin, qty in data["positions"].items():
            price = self._price(coin)
            if price is not None:
                lines.append(f"  {coin:<15s} {qty:>12g}  @ ${price:,.2f}  = ${qty * price:,.2f}")
            else:
                lines.append(f"  {coin:<15s} {qty:>12g}  (price unavailable)")
        return "\n".join(lines)

    @safe
    def cmd_history(self, arg=""):
        """Trade log"""
        data = self._load()
        if not data["trades"]:
            return "[paper] No trades yet."
        lines = [f"[paper] {len(data['trades'])} trade(s):"]
        for t in data["trades"][-30:]:
            lines.append(f"  [{t['at']}] {t['side'].upper():<4s} {t['qty']:g} {t['coin']} "
                        f"@ ${t['price']:,.2f} (${t['usd']:,.2f})")
        return "\n".join(lines)

    @safe
    def cmd_networth(self, arg=""):
        """Cash + positions at current prices"""
        data = self._load()
        total = data["cash"]
        lines = [f"[paper] Cash: ${data['cash']:,.2f}"]
        for coin, qty in data["positions"].items():
            price = self._price(coin)
            if price is not None:
                value = qty * price
                total += value
                lines.append(f"  + {coin}: ${value:,.2f}")
        lines.append(f"\n  Net worth: ${total:,.2f}  (started at $10,000.00 by default)")
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
