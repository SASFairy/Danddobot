import os
import json
import shutil
import sqlite3
import logging
import asyncio
from typing import Optional, Dict, Any

logger = logging.getLogger("danddobot.db_manager")

class DatabaseManager:
    """
    Manager for JSON-based database to store user info and mini-game data.
    Provides direct, human-readable file edit capabilities while maintaining 
    100% backward compatibility with sqlite3 signatures and thread safety.
    """
    def __init__(self, db_path: str = "config/game_database.json"):
        self.db_path = db_path
        self._lock = None
        self.data = {"users": {}}
        self._init_db()

    def get_lock(self) -> asyncio.Lock:
        """Lazily instantiates the asyncio.Lock within the active event loop."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _init_db(self):
        """Initializes database, handles automatic migration from SQLite to JSON if needed."""
        try:
            # 1. Determine if we need to migrate from SQLite
            old_db_path = "config/game_database.db"
            backup_db_path = "config/game_database.db.bak"
            sqlite_to_migrate = None
            
            # We migrate if JSON doesn't exist or is empty
            json_exists = os.path.exists(self.db_path) and os.path.getsize(self.db_path) > 0
            if not json_exists:
                if os.path.exists(old_db_path):
                    sqlite_to_migrate = old_db_path
                elif os.path.exists(backup_db_path):
                    sqlite_to_migrate = backup_db_path
            
            if sqlite_to_migrate:
                logger.info(f"SQLite database found at {sqlite_to_migrate}. Automatic migration to JSON starting...")
                try:
                    conn = sqlite3.connect(sqlite_to_migrate)
                    cursor = conn.cursor()
                    
                    # Verify if users table exists
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
                    if cursor.fetchone():
                        cursor.execute("SELECT * FROM users")
                        columns = [col[0] for col in cursor.description]
                        rows = cursor.fetchall()
                        
                        migrated_users = {}
                        for row in rows:
                            user_data = dict(zip(columns, row))
                            user_id = user_data.pop("user_id")
                            
                            # Parse items JSON string representation to array
                            items_str = user_data.get("items", "[]")
                            try:
                                user_data["items"] = json.loads(items_str)
                            except Exception:
                                user_data["items"] = []
                                
                            migrated_users[str(user_id)] = user_data
                        
                        self.data = {"users": migrated_users}
                        self._save_data_sync()
                        logger.info(f"Successfully migrated {len(migrated_users)} users from SQLite ({sqlite_to_migrate}) to JSON database.")
                        
                        conn.close()
                        # Safe backup rename only if migrating the active db file
                        if sqlite_to_migrate == old_db_path:
                            shutil.move(old_db_path, backup_db_path)
                            logger.info(f"Old SQLite database has been backed up and renamed to {backup_db_path}")
                        return  # Exit early since we just performed a successful migration and saved!
                    else:
                        logger.warning(f"SQLite database at {sqlite_to_migrate} does not contain 'users' table. Skipping migration.")
                        conn.close()
                except Exception as migration_err:
                    logger.error(f"Error during SQLite to JSON database migration: {migration_err}")
            
            # 2. Load JSON database if exists, otherwise initialize empty
            if os.path.exists(self.db_path) and os.path.getsize(self.db_path) > 0:
                try:
                    with open(self.db_path, "r", encoding="utf-8") as f:
                        loaded_data = json.load(f)
                        if isinstance(loaded_data, dict) and "users" in loaded_data:
                            self.data = loaded_data
                            logger.info(f"Loaded JSON database from {self.db_path} successfully. ({len(self.data['users'])} users)")
                        else:
                            logger.warning(f"Database file at {self.db_path} has an invalid structure. Resetting database.")
                            self.data = {"users": {}}
                            self._save_data_sync()
                except json.JSONDecodeError as je:
                    logger.error(f"JSON Decode Error in {self.db_path}: {je}. The file might be corrupted. Resetting with safe defaults.")
                    self.data = {"users": {}}
                    self._save_data_sync()
            else:
                self.data = {"users": {}}
                self._save_data_sync()
                logger.info(f"Created new empty JSON database at {self.db_path}.")
                
        except Exception as e:
            logger.critical(f"Failed to initialize JSON database at {self.db_path}: {e}")

    async def _save_data(self):
        """Saves database in-memory dict to the JSON file asynchronously and atomically."""
        await asyncio.to_thread(self._save_data_sync)

    def _save_data_sync(self):
        """Saves database in-memory dict to the JSON file synchronously and atomically."""
        try:
            dir_name = os.path.dirname(self.db_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
                
            temp_path = self.db_path + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, ensure_ascii=False, indent=4)
                
            os.replace(temp_path, self.db_path)
        except Exception as e:
            logger.error(f"Failed to write JSON database to {self.db_path}: {e}")

    async def register_user(self, user_id: int, username: str) -> bool:
        """Registers a new user with 50,000 won if they don't exist yet."""
        async with self.get_lock():
            uid_str = str(user_id)
            if uid_str in self.data["users"]:
                return False  # Already registered
            
            from datetime import datetime
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            self.data["users"][uid_str] = {
                "username": username,
                "money": 50000,
                "items": [],
                "created_at": now_str,
                "last_checkin": None,
                "checkin_streak": 0,
                "last_begging": None,
                "last_teaching": None
            }
            await self._save_data()
            logger.info(f"User {username} (ID: {user_id}) registered successfully in database.")
            return True

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves user information from database."""
        async with self.get_lock():
            uid_str = str(user_id)
            user_data = self.data["users"].get(uid_str)
            if user_data:
                # Return a copy to prevent in-memory mutation side effects
                res = {
                    "user_id": user_id,
                    "username": user_data.get("username", ""),
                    "money": user_data.get("money", 50000),
                    "items": user_data.get("items", []),
                    "created_at": user_data.get("created_at", ""),
                    "last_checkin": user_data.get("last_checkin"),
                    "checkin_streak": user_data.get("checkin_streak", 0),
                    "last_begging": user_data.get("last_begging"),
                    "last_teaching": user_data.get("last_teaching")
                }
                # Ensure items is returned as JSON string for compatibility with existing command modules
                if isinstance(res["items"], (list, dict)):
                    res["items"] = json.dumps(res["items"], ensure_ascii=False)
                return res
            return None

    async def get_user_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieves user information from database by username (case-insensitive fuzzy match)."""
        async with self.get_lock():
            name_lower = name.lower()
            for uid_str, user_data in self.data["users"].items():
                if name_lower in user_data.get("username", "").lower():
                    res = {
                        "user_id": int(uid_str),
                        "username": user_data.get("username", ""),
                        "money": user_data.get("money", 50000),
                        "items": user_data.get("items", []),
                        "created_at": user_data.get("created_at", ""),
                        "last_checkin": user_data.get("last_checkin"),
                        "checkin_streak": user_data.get("checkin_streak", 0),
                        "last_begging": user_data.get("last_begging"),
                        "last_teaching": user_data.get("last_teaching")
                    }
                    if isinstance(res["items"], (list, dict)):
                        res["items"] = json.dumps(res["items"], ensure_ascii=False)
                    return res
            return None

    async def update_money(self, user_id: int, amount_change: int) -> Optional[int]:
        """Updates user money (can be positive or negative) and returns the new total."""
        async with self.get_lock():
            uid_str = str(user_id)
            user_data = self.data["users"].get(uid_str)
            if not user_data:
                return None  # User not found
            
            current_money = user_data.get("money", 50000)
            new_money = current_money + amount_change
            if new_money < 0:
                return -1  # Insufficient funds
            
            user_data["money"] = new_money
            await self._save_data()
            logger.debug(f"User {user_id} money updated: {current_money} -> {new_money} (change: {amount_change})")
            return new_money

    async def buy_item(self, user_id: int, item_name: str, price: int) -> Dict[str, Any]:
        """
        Deducts money and adds item to user's inventory in a thread-safe atomic transaction.
        Returns outcome status dictionary.
        """
        async with self.get_lock():
            uid_str = str(user_id)
            user_data = self.data["users"].get(uid_str)
            if not user_data:
                return {"status": "not_registered"}
                
            current_money = user_data.get("money", 50000)
            if current_money < price:
                return {"status": "insufficient_funds", "money": current_money}
                
            # Deduct funds
            user_data["money"] = current_money - price
            
            # Update inventory list with quantity representation
            items_list = user_data.get("items", [])
            import re
            found = False
            for idx, item_str in enumerate(items_list):
                # Match exact name followed optionally by space and quantity
                if item_str == item_name or item_str.startswith(f"{item_name} "):
                    match = re.search(r"\((?P<qty>\d+)개\)", item_str)
                    qty = 1
                    if match:
                        qty = int(match.group("qty"))
                    items_list[idx] = f"{item_name} ({qty + 1}개)"
                    found = True
                    break
                    
            if not found:
                items_list.append(f"{item_name} (1개)")
                
            user_data["items"] = items_list
            await self._save_data()
            
            return {
                "status": "success",
                "money": user_data["money"],
                "items": items_list
            }

    async def checkin_user(self, user_id: int, today_str: str, yesterday_str: str) -> Dict[str, Any]:
        """
        Executes daily check-in inside a safe transaction.
        Returns check-in outcome status and updated fields.
        """
        async with self.get_lock():
            uid_str = str(user_id)
            user_data = self.data["users"].get(uid_str)
            if not user_data:
                return {"status": "not_registered"}
            
            current_money = user_data.get("money", 50000)
            last_checkin = user_data.get("last_checkin")
            streak = user_data.get("checkin_streak", 0)
            username = user_data.get("username", "")
            
            # Check if already checked in today
            if last_checkin == today_str:
                return {
                    "status": "already",
                    "money": current_money,
                    "streak": streak
                }
            
            # Determine consecutive streak and payout
            new_streak = 1
            reward = 10000
            is_bonus = False
            
            if last_checkin == yesterday_str:
                new_streak = streak + 1
                if new_streak == 7:
                    reward = 100000
                    is_bonus = True
                    # Reset the streak to 0 after this bonus check-in so next starts fresh 7-day cycle.
                    new_streak_db = 0
                else:
                    new_streak_db = new_streak
            else:
                new_streak_db = 1
            
            new_money = current_money + reward
            
            # Update user fields
            user_data["money"] = new_money
            user_data["last_checkin"] = today_str
            user_data["checkin_streak"] = new_streak_db
            
            await self._save_data()
            logger.info(f"User {username} (ID: {user_id}) checked in. Day: {today_str}, Streak: {new_streak_db}, Reward: {reward}")
            
            return {
                "status": "success",
                "reward": reward,
                "is_bonus": is_bonus,
                "money": new_money,
                "streak": new_streak
            }

    async def get_db_stats(self) -> Dict[str, Any]:
        """Returns overall database statistics (total users, total money pool, db size)."""
        async with self.get_lock():
            users = self.data.get("users", {})
            count = len(users)
            total_money = sum(u.get("money", 50000) for u in users.values())
            db_size = os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
            return {
                "total_users": count,
                "total_money": total_money,
                "db_size": db_size
            }

    async def get_top_users(self, limit: int = 5) -> list:
        """Retrieves top richest users."""
        async with self.get_lock():
            users_list = []
            for uid_str, user_data in self.data.get("users", {}).items():
                users_list.append({
                    "user_id": int(uid_str),
                    "username": user_data.get("username", ""),
                    "money": user_data.get("money", 50000),
                    "streak": user_data.get("checkin_streak", 0)
                })
            # Sort by money descending
            users_list.sort(key=lambda x: x["money"], reverse=True)
            return users_list[:limit]

    async def admin_update_user(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """
        Dynamically updates user fields in the database for administrative purposes.
        updates dictionary keys: 'money', 'checkin_streak', 'last_checkin', 'items', 'username'.
        """
        if not updates:
            return False
            
        async with self.get_lock():
            uid_str = str(user_id)
            user_data = self.data["users"].get(uid_str)
            if not user_data:
                return False
            
            for key, val in updates.items():
                if key == "items":
                    if isinstance(val, str):
                        try:
                            val = json.loads(val)
                        except Exception:
                            pass
                user_data[key] = val
                
            await self._save_data()
            logger.warning(f"Admin dynamically updated user {user_id} fields: {updates}")
            return True

    async def transfer_rps_money(self, winner_id: int, loser_id: int, bet_amount: int, profit: int) -> bool:
        """
        Atomically transfers the bet money between players for Rock-Paper-Scissors, 
        accounting for system commission.
        """
        async with self.get_lock():
            winner_str = str(winner_id)
            loser_str = str(loser_id)
            
            winner_data = self.data["users"].get(winner_str)
            loser_data = self.data["users"].get(loser_str)
            
            if not winner_data or not loser_data:
                return False
                
            loser_money = loser_data.get("money", 50000)
            if loser_money < bet_amount:
                return False
                
            winner_money = winner_data.get("money", 50000)
            
            loser_data["money"] = loser_money - bet_amount
            winner_data["money"] = winner_money + profit
            
            await self._save_data()
            logger.info(f"RPS Transfer Success: Winner {winner_id} (+{profit}), Loser {loser_id} (-{bet_amount})")
            return True

    async def update_begging_time(self, user_id: int, timestamp_str: str) -> bool:
        """Updates last_begging timestamp string for a user."""
        async with self.get_lock():
            uid_str = str(user_id)
            user_data = self.data["users"].get(uid_str)
            if not user_data:
                return False
            user_data["last_begging"] = timestamp_str
            await self._save_data()
            return True

    async def update_teaching_time(self, user_id: int, timestamp_str: str) -> bool:
        """Updates last_teaching timestamp string for a user."""
        async with self.get_lock():
            uid_str = str(user_id)
            user_data = self.data["users"].get(uid_str)
            if not user_data:
                return False
            user_data["last_teaching"] = timestamp_str
            await self._save_data()
            return True
