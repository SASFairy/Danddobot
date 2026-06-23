import os
import json
import logging
import asyncio
from typing import Any

logger = logging.getLogger("danddobot.state_manager")

class StateManager:
    """
    Centralized, thread-safe, and cached manager for Danddobot persistent configuration state.
    Eliminates duplicated file I/O operations across bot and UI files.
    """
    def __init__(self, state_path: str = "config/state.json"):
        self.state_path = state_path
        self._lock = asyncio.Lock()  # Guarantees atomic, non-overlapping writes
        self._cache: dict[str, Any] = {}
        
        # Load initially from disk synchronously on startup during application boot
        self._load_state()

    def _load_state(self):
        """Loads state.json from disk into the in-memory cache."""
        if not os.path.exists(self.state_path):
            logger.info(f"State file {self.state_path} does not exist. Starting with empty configuration.")
            self._cache = {}
            return

        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
            logger.info(f"Successfully loaded and cached state from {self.state_path}: {self._cache}")
        except Exception as e:
            logger.error(f"Failed to read state file at {self.state_path}: {e}. Initializing empty cache.")
            self._cache = {}

    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Retrieves a value from the in-memory cache instantly with zero disk read overhead.
        """
        return self._cache.get(key, default)

    async def set_value(self, key: str, value: Any):
        """
        Updates the key in the in-memory cache and triggers a thread-safe atomic disk write.
        """
        self._cache[key] = value
        await self._save_state()

    async def _save_state(self):
        """Writes the cached state back to disk atomically under a lock."""
        async with self._lock:  # Only one task can write to the disk at any given time
            try:
                # Ensure parent directory exists
                os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
                
                # Write to a temporary file first, then rename it.
                # (Standard software engineering best-practice for corruption-proof atomic writes)
                temp_path = f"{self.state_path}.tmp"
                with open(temp_path, "w", encoding="utf-8") as f:
                    json.dump(self._cache, f, indent=4)
                
                # Replace the old file with the successfully completed temp file
                os.replace(temp_path, self.state_path)
                logger.debug(f"Atomically persisted updated state to {self.state_path}")
            except Exception as e:
                logger.error(f"Failed to save state to {self.state_path}: {e}")
