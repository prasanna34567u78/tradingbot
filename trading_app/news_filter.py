"""
Economic News Filter Module
============================
Fetches high-impact economic calendar events (e.g. FOMC, CPI, NFP, Interest Rate decisions)
and provides real-time checks to prevent entries before, during, and after high-impact volatility events.
Supports caching and graceful offline fallback.
"""

import time
import json
import logging
import urllib.request
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

logger = logging.getLogger('gold_trading_bot')

class EconomicNewsFilter:
    def __init__(self, buffer_before_minutes: int = 30, buffer_after_minutes: int = 30):
        self.buffer_before = timedelta(minutes=buffer_before_minutes)
        self.buffer_after = timedelta(minutes=buffer_after_minutes)
        self.last_fetch_time = 0.0
        self.cache_ttl_seconds = 3600 * 4  # Refresh every 4 hours
        self.high_impact_events: List[Dict[str, Any]] = []
        self.calendar_url = 'https://nfs.faireconomy.media/ff_calendar_thisweek.json'
        
        # Currency relevance mapping
        self.currency_map = {
            'XAUUSDm': ['USD', 'All'],
            'BTCUSDm': ['USD', 'All'],
            'USTECm':  ['USD', 'All'],
            'US30m':   ['USD', 'All'],
            'US500m':  ['USD', 'All'],
            'EURUSDm': ['USD', 'EUR', 'All'],
            'GBPUSDm': ['USD', 'GBP', 'All'],
            'USDJPYm': ['USD', 'JPY', 'All'],
            'GBPJPYm': ['GBP', 'JPY', 'All'],
            'USOILm':  ['USD', 'All'],
        }
        
        # Initial background fetch
        self._refresh_calendar()

    def _refresh_calendar(self):
        """Fetch weekly calendar from ForexFactory JSON feed."""
        now = time.time()
        if now - self.last_fetch_time < self.cache_ttl_seconds and self.high_impact_events:
            return

        try:
            req = urllib.request.Request(
                self.calendar_url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                raw = resp.read().decode('utf-8')
                data = json.loads(raw)
                
                parsed_events = []
                for item in data:
                    # Filter for High Impact events only (red folder)
                    if item.get('impact') != 'High':
                        continue
                        
                    date_str = item.get('date', '')
                    if not date_str:
                        continue
                        
                    try:
                        # ForexFactory format: 2026-09-16T14:00:00-04:00 (ISO with offset)
                        event_dt = datetime.fromisoformat(date_str).astimezone(timezone.utc)
                        parsed_events.append({
                            'title': item.get('title', 'Economic Event'),
                            'country': item.get('country', 'USD'),
                            'impact': item.get('impact', 'High'),
                            'datetime_utc': event_dt
                        })
                    except Exception as parse_err:
                        continue
                        
                self.high_impact_events = parsed_events
                self.last_fetch_time = now
                logger.info(f"[NewsFilter] Successfully loaded {len(self.high_impact_events)} High-Impact news events for this week.")
        except Exception as e:
            logger.warning(f"[NewsFilter] Could not fetch economic calendar: {e}. Trading will proceed with caution.")

    def is_news_blackout(self, symbol: str) -> tuple:
        """
        Check if current time is within blackout buffer (e.g. ±30 minutes) of a High-Impact news release.
        Returns: (is_blackout: bool, event_info: str)
        """
        self._refresh_calendar()
        if not self.high_impact_events:
            return False, ""

        now_utc = datetime.now(timezone.utc)
        relevant_currencies = self.currency_map.get(symbol, ['USD', 'All'])

        for ev in self.high_impact_events:
            if ev['country'] not in relevant_currencies:
                continue

            ev_time = ev['datetime_utc']
            start_blackout = ev_time - self.buffer_before
            end_blackout = ev_time + self.buffer_after

            if start_blackout <= now_utc <= end_blackout:
                time_diff = int((ev_time - now_utc).total_seconds() / 60)
                timing_str = f"in {time_diff} mins" if time_diff > 0 else f"{abs(time_diff)} mins ago"
                info = f"{ev['title']} ({ev['country']}) at {ev_time.strftime('%H:%M UTC')} ({timing_str})"
                return True, info

        return False, ""
