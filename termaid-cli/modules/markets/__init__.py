"""Markets Module — Read-only crypto and stock data, watchlists, portfolio tracking.

Crypto prices come from CoinGecko's free public API (no key required). Stock
data needs a paid/keyed API this reconstruction doesn't have credentials for,
so stock commands are intentionally out of scope here — crypto is fully
real; a stock backend can be added later behind the same command shape.

Commands (~14):
  /markets price <coin>              Current price (USD) for a coin, e.g. bitcoin
  /markets top [n]                     Top n coins by market cap (default 10)
  /markets watch <coin>                  Add a coin to your watchlist
  /markets unwatch <coin>                  Remove a coin from your watchlist
  /markets watchlist                         Show your watchlist with current prices
  /markets portfolio-add <coin> <qty>          Record a holding
  /markets portfolio-remove <coin>               Remove a holding
  /markets portfolio                               Show holdings + current value
  /markets convert <amount> <from> <to>              Convert between two coins/currencies
  /markets explain                                     How this module works
"""

import json
import os
import sys
from pathlib import Path
from termaid.extensions.modules import Module

try:
    from _shared.error_helper import safe
except ImportError:
    def safe(fn): return fn

_API = "https://api.coingecko.com/api/v3"


class MarketsModule(Module):
    name = "markets"
    version = "1.0.0"
    description = "Read-only crypto and stock data, watchlists, portfolio tracking, education"
    author = "termaid"

    def on_load(self):
        for cmd in ["price", "top", "watch", "unwatch", "watchlist",
                    "portfolio-add", "portfolio-remove", "portfolio",
                    "convert", "explain"]:
            self.register_command(cmd, getattr(self, f"cmd_{cmd.replace('-', '_')}"))

        home = Path.home()
        if sys.platform == "win32":
            data_dir = Path(os.environ.get("APPDATA", str(home / "AppData/Roaming"))) / "termaid"
        else:
            data_dir = home / ".termaid"
        self._dir = data_dir / "markets"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._watchlist_file = self._dir / "watchlist.json"
        self._portfolio_file = self._dir / "portfolio.json"

    def _load_json(self, path: Path, default):
        if path.exists():
            try:
                return json.loads(path.read_text())
            except Exception:
                pass
        return default

    def _get_prices(self, coin_ids: list[str]) -> dict:
        """{'bitcoin': 12345.0, ...}. Missing IDs are simply absent from the result."""
        try:
            import httpx
        except ImportError:
            return {}
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(f"{_API}/simple/price", params={
                    "ids": ",".join(coin_ids), "vs_currencies": "usd",
                })
                r.raise_for_status()
                data = r.json()
        except Exception:
            return {}
        return {k: v.get("usd") for k, v in data.items() if "usd" in v}

    @safe
    def cmd_price(self, arg=""):
        """Current price (USD) for a coin, e.g. bitcoin"""
        coin = (arg or "").strip().lower()
        if not coin:
            return "[markets] Usage: /markets price <coin-id>  e.g. /markets price bitcoin"
        prices = self._get_prices([coin])
        if coin not in prices:
            return f"[markets] No price found for '{coin}' (use CoinGecko IDs, e.g. bitcoin, ethereum)"
        return f"[markets] {coin}: ${prices[coin]:,.2f}"

    @safe
    def cmd_top(self, arg=""):
        """Top n coins by market cap (default 10)"""
        try:
            n = int((arg or "10").strip())
        except Exception:
            n = 10
        n = max(1, min(n, 50))
        try:
            import httpx
        except ImportError:
            return "[markets] httpx not installed."
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.get(f"{_API}/coins/markets", params={
                    "vs_currency": "usd", "order": "market_cap_desc", "per_page": n, "page": 1,
                })
                r.raise_for_status()
                coins = r.json()
        except Exception as e:
            return f"[markets] Request failed: {e}"
        lines = [f"[markets] Top {len(coins)} by market cap:"]
        for c in coins:
            lines.append(f"  {c['symbol'].upper():<6s} ${c['current_price']:>12,.2f}   {c['name']}")
        return "\n".join(lines)

    @safe
    def cmd_watch(self, arg=""):
        """Add a coin to your watchlist"""
        coin = (arg or "").strip().lower()
        if not coin:
            return "[markets] Usage: /markets watch <coin-id>"
        watchlist = self._load_json(self._watchlist_file, [])
        if coin not in watchlist:
            watchlist.append(coin)
            self._watchlist_file.write_text(json.dumps(watchlist, indent=2))
        return f"[markets] Watching '{coin}'"

    @safe
    def cmd_unwatch(self, arg=""):
        """Remove a coin from your watchlist"""
        coin = (arg or "").strip().lower()
        watchlist = self._load_json(self._watchlist_file, [])
        if coin not in watchlist:
            return f"[markets] '{coin}' isn't on your watchlist"
        watchlist.remove(coin)
        self._watchlist_file.write_text(json.dumps(watchlist, indent=2))
        return f"[markets] Removed '{coin}'"

    @safe
    def cmd_watchlist(self, arg=""):
        """Show your watchlist with current prices"""
        watchlist = self._load_json(self._watchlist_file, [])
        if not watchlist:
            return "[markets] Watchlist is empty. /markets watch <coin-id>"
        prices = self._get_prices(watchlist)
        lines = [f"[markets] Watchlist ({len(watchlist)}):"]
        for coin in watchlist:
            price = prices.get(coin)
            lines.append(f"  {coin:<15s} {'$' + format(price, ',.2f') if price is not None else 'unavailable'}")
        return "\n".join(lines)

    @safe
    def cmd_portfolio_add(self, arg=""):
        """Record a holding: /markets portfolio-add <coin> <qty>"""
        parts = (arg or "").split()
        if len(parts) != 2:
            return "[markets] Usage: /markets portfolio-add <coin-id> <quantity>"
        coin, qty_s = parts[0].lower(), parts[1]
        try:
            qty = float(qty_s)
        except Exception:
            return "[markets] Quantity must be a number"
        portfolio = self._load_json(self._portfolio_file, {})
        portfolio[coin] = portfolio.get(coin, 0.0) + qty
        self._portfolio_file.write_text(json.dumps(portfolio, indent=2))
        return f"[markets] Holding updated: {coin} = {portfolio[coin]:g}"

    @safe
    def cmd_portfolio_remove(self, arg=""):
        """Remove a holding entirely"""
        coin = (arg or "").strip().lower()
        portfolio = self._load_json(self._portfolio_file, {})
        if coin not in portfolio:
            return f"[markets] No holding for '{coin}'"
        del portfolio[coin]
        self._portfolio_file.write_text(json.dumps(portfolio, indent=2))
        return f"[markets] Removed holding '{coin}'"

    @safe
    def cmd_portfolio(self, arg=""):
        """Show holdings + current value"""
        portfolio = self._load_json(self._portfolio_file, {})
        if not portfolio:
            return "[markets] No holdings yet. /markets portfolio-add <coin> <qty>"
        prices = self._get_prices(list(portfolio.keys()))
        lines = ["[markets] Portfolio:"]
        total = 0.0
        for coin, qty in portfolio.items():
            price = prices.get(coin)
            if price is not None:
                value = price * qty
                total += value
                lines.append(f"  {coin:<15s} {qty:>10g}  @ ${price:,.2f}  = ${value:,.2f}")
            else:
                lines.append(f"  {coin:<15s} {qty:>10g}  (price unavailable)")
        lines.append(f"\n  Total (priced holdings): ${total:,.2f}")
        return "\n".join(lines)

    @safe
    def cmd_convert(self, arg=""):
        """Convert between two coins/currencies: /markets convert <amount> <from> <to>"""
        parts = (arg or "").split()
        if len(parts) != 3:
            return "[markets] Usage: /markets convert <amount> <from-coin> <to-coin>"
        try:
            amount = float(parts[0])
        except Exception:
            return "[markets] Amount must be a number"
        from_coin, to_coin = parts[1].lower(), parts[2].lower()
        prices = self._get_prices([from_coin, to_coin])
        if from_coin not in prices or to_coin not in prices:
            return f"[markets] Could not price both '{from_coin}' and '{to_coin}'"
        usd_value = amount * prices[from_coin]
        result = usd_value / prices[to_coin]
        return f"[markets] {amount:g} {from_coin} = {result:g} {to_coin} (via USD)"

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
