import os
import json
import logging
import asyncio
from typing import Dict, Any

logger = logging.getLogger("danddobot.item_db_manager")

class ItemDatabaseManager:
    def __init__(self, db_path: str = "config/item_database.json"):
        self.db_path = db_path
        self.lock = asyncio.Lock()
        self.data = {"items": {}}
        self._load_data()

    def _load_data(self):
        """Loads item database from JSON file, initializing with default test items if empty/missing."""
        try:
            dir_name = os.path.dirname(self.db_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
                
            if not os.path.exists(self.db_path) or os.path.getsize(self.db_path) == 0:
                self.data = {
                    "items": {
                        "참치 통조림": {
                            "price": 5000000,
                            "description": "단또가 가장 좋아하는 기름진 참치 통조림이다냥!"
                        },
                        "츄르": {
                            "price": 10000000,
                            "description": "설명이 필요 없는 고양이계의 최고 존엄 마약 간식이다냥!"
                        }
                    }
                }
                self._save_data_sync()
                logger.info("Initialized default item_database.json with test items.")
            else:
                with open(self.db_path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                if "items" not in self.data:
                    self.data = {"items": {}}
        except Exception as e:
            logger.error(f"Failed to load item database: {e}")
            self.data = {"items": {}}

    def _save_data_sync(self):
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    async def _save_data(self):
        await asyncio.to_thread(self._save_data_sync)

    def get_lock(self):
        return self.lock

    async def get_items(self) -> Dict[str, Any]:
        """Returns all items from the database."""
        async with self.lock:
            return self.data.get("items", {})

    async def update_item(self, name: str, price: int, description: str) -> bool:
        """Adds or updates an item in the item database."""
        async with self.lock:
            if "items" not in self.data:
                self.data["items"] = {}
            self.data["items"][name] = {
                "price": price,
                "description": description
            }
            await self._save_data()
            return True

    async def delete_item(self, name: str) -> bool:
        """Deletes an item from the database."""
        async with self.lock:
            items = self.data.get("items", {})
            if name in items:
                del items[name]
                await self._save_data()
                return True
            return False
