import sqlite3
import os
import logging
import asyncio
from typing import Optional, Dict, Any

logger = logging.getLogger("danddobot.db_manager")

class DatabaseManager:
    """
    Manager for sqlite3 database to store user info and mini-game data.
    Runs blocking database operations in asyncio.to_thread to keep the Discord event loop non-blocking.
    """
    def __init__(self, db_path: str = "config/game_database.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initializes SQLite database, creates tables, and performs migrations if needed."""
        try:
            # Ensure the directory exists
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 1. Create main users table if not exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT NOT NULL,
                    money INTEGER DEFAULT 50000,
                    items TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
            
            # 2. Database Migration: Add columns for check-in feature if they are missing
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN last_checkin TEXT")
                cursor.execute("ALTER TABLE users ADD COLUMN checkin_streak INTEGER DEFAULT 0")
                conn.commit()
                logger.info("Successfully executed DB migration: added check-in columns to users table.")
            except sqlite3.OperationalError:
                # OperationalError occurs if columns already exist. This is expected on secondary boots.
                logger.debug("Check-in columns already exist in users table. Skipping migration.")

            # 3. Database Migration: Add columns for begging feature if they are missing
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN last_begging TEXT")
                conn.commit()
                logger.info("Successfully executed DB migration: added last_begging column to users table.")
            except sqlite3.OperationalError:
                logger.debug("last_begging column already exists in users table. Skipping migration.")

            # 4. Database Migration: Add columns for teaching feature if they are missing
            try:
                cursor.execute("ALTER TABLE users ADD COLUMN last_teaching TEXT")
                conn.commit()
                logger.info("Successfully executed DB migration: added last_teaching column to users table.")
            except sqlite3.OperationalError:
                logger.debug("last_teaching column already exists in users table. Skipping migration.")

            conn.close()
            logger.info(f"Database initialized successfully at {self.db_path}.")
        except Exception as e:
            logger.critical(f"Failed to initialize SQLite database at {self.db_path}: {e}")

    async def register_user(self, user_id: int, username: str) -> bool:
        """Registers a new user with 50,000 won if they don't exist yet."""
        def _query():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                # Check if user already exists
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                if cursor.fetchone():
                    return False  # Already registered
                
                cursor.execute(
                    "INSERT INTO users (user_id, username, money, items, checkin_streak) VALUES (?, ?, 50000, '[]', 0)",
                    (user_id, username)
                )
                conn.commit()
                logger.info(f"User {username} (ID: {user_id}) registered successfully in database.")
                return True
            except Exception as e:
                logger.error(f"Error registering user {user_id} ({username}): {e}")
                return False
            finally:
                conn.close()
        
        return await asyncio.to_thread(_query)

    async def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves user information from database."""
        def _query():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, username, money, items, 
                           datetime(created_at, 'localtime'), last_checkin, checkin_streak, last_begging, last_teaching 
                    FROM users WHERE user_id = ?
                """, (user_id,))
                row = cursor.fetchone()
                if row:
                    return {
                        "user_id": row[0],
                        "username": row[1],
                        "money": row[2],
                        "items": row[3],
                        "created_at": row[4],
                        "last_checkin": row[5],
                        "checkin_streak": row[6],
                        "last_begging": row[7],
                        "last_teaching": row[8]
                    }
                return None
            except Exception as e:
                logger.error(f"Error fetching user {user_id} from database: {e}")
                return None
            finally:
                conn.close()
        
        return await asyncio.to_thread(_query)

    async def get_user_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Retrieves user information from database by username (case-insensitive fuzzy match)."""
        def _query():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, username, money, items, 
                           datetime(created_at, 'localtime'), last_checkin, checkin_streak, last_begging, last_teaching 
                    FROM users WHERE username LIKE ? LIMIT 1
                """, (f"%{name}%",))
                row = cursor.fetchone()
                if row:
                    return {
                        "user_id": row[0],
                        "username": row[1],
                        "money": row[2],
                        "items": row[3],
                        "created_at": row[4],
                        "last_checkin": row[5],
                        "checkin_streak": row[6],
                        "last_begging": row[7],
                        "last_teaching": row[8]
                    }
                return None
            except Exception as e:
                logger.error(f"Error fetching user by name {name} from database: {e}")
                return None
            finally:
                conn.close()
        
        return await asyncio.to_thread(_query)

    async def update_money(self, user_id: int, amount_change: int) -> Optional[int]:
        """Updates user money (can be positive or negative) and returns the new total."""
        def _query():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT money FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if not row:
                    return None  # User not found
                
                current_money = row[0]
                new_money = current_money + amount_change
                if new_money < 0:
                    return -1  # Insufficient funds
                
                cursor.execute("UPDATE users SET money = ? WHERE user_id = ?", (new_money, user_id))
                conn.commit()
                logger.debug(f"User {user_id} money updated: {current_money} -> {new_money} (change: {amount_change})")
                return new_money
            except Exception as e:
                logger.error(f"Error updating money for user {user_id}: {e}")
                return None
            finally:
                conn.close()
        
        return await asyncio.to_thread(_query)

    async def checkin_user(self, user_id: int, today_str: str, yesterday_str: str) -> Dict[str, Any]:
        """
        Executes daily check-in inside a safe SQLite transaction.
        Returns check-in outcome status and updated fields.
        """
        def _query():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                
                # 1. Verify if user exists
                cursor.execute("SELECT money, last_checkin, checkin_streak, username FROM users WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if not row:
                    return {"status": "not_registered"}
                
                current_money, last_checkin, streak, username = row
                
                # 2. Check if already checked in today
                if last_checkin == today_str:
                    return {
                        "status": "already",
                        "money": current_money,
                        "streak": streak
                    }
                
                # 3. Determine consecutive streak and payout
                new_streak = 1
                reward = 10000
                is_bonus = False
                
                if last_checkin == yesterday_str:
                    new_streak = streak + 1
                    if new_streak == 7:
                        reward = 100000
                        is_bonus = True
                        # Note: We'll set the new streak to 0 after this bonus check-in
                        # so that they start a new 7-day cycle on the next day.
                        new_streak_db = 0
                    else:
                        new_streak_db = new_streak
                else:
                    new_streak_db = 1
                
                new_money = current_money + reward
                
                # Update user fields
                cursor.execute(
                    "UPDATE users SET money = ?, last_checkin = ?, checkin_streak = ? WHERE user_id = ?",
                    (new_money, today_str, new_streak_db, user_id)
                )
                conn.commit()
                logger.info(f"User {username} (ID: {user_id}) checked in. Day: {today_str}, Streak: {new_streak_db}, Reward: {reward}")
                
                return {
                    "status": "success",
                    "reward": reward,
                    "is_bonus": is_bonus,
                    "money": new_money,
                    "streak": new_streak
                }
            except Exception as e:
                logger.error(f"Error checking in user {user_id}: {e}")
                return {"status": "error", "error": str(e)}
            finally:
                conn.close()
                
        return await asyncio.to_thread(_query)

    async def get_db_stats(self) -> Dict[str, Any]:
        """Returns overall database statistics (total users, total money pool, db size)."""
        def _query():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*), SUM(money) FROM users")
                count, total_money = cursor.fetchone()
                return {
                    "total_users": count or 0,
                    "total_money": total_money or 0,
                    "db_size": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0
                }
            except Exception as e:
                logger.error(f"Error fetching DB stats: {e}")
                return {"total_users": 0, "total_money": 0, "db_size": 0}
            finally:
                conn.close()
        return await asyncio.to_thread(_query)

    async def get_top_users(self, limit: int = 5) -> list:
        """Retrieves top richest users."""
        def _query():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT user_id, username, money, checkin_streak 
                    FROM users 
                    ORDER BY money DESC 
                    LIMIT ?
                """, (limit,))
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    result.append({
                        "user_id": row[0],
                        "username": row[1],
                        "money": row[2],
                        "streak": row[3]
                    })
                return result
            except Exception as e:
                logger.error(f"Error fetching top users: {e}")
                return []
            finally:
                conn.close()
        return await asyncio.to_thread(_query)

    async def admin_update_user(self, user_id: int, updates: Dict[str, Any]) -> bool:
        """
        Dynamically updates user fields in the database for administrative purposes.
        updates dictionary keys: 'money', 'checkin_streak', 'last_checkin', 'items', 'username'.
        """
        if not updates:
            return False
            
        def _query():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                
                # Check if user exists
                cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
                if not cursor.fetchone():
                    return False
                
                # Build dynamic query
                set_clauses = []
                params = []
                for key, val in updates.items():
                    set_clauses.append(f"{key} = ?")
                    params.append(val)
                
                params.append(user_id)
                query_str = f"UPDATE users SET {', '.join(set_clauses)} WHERE user_id = ?"
                
                cursor.execute(query_str, tuple(params))
                conn.commit()
                logger.warning(f"Admin dynamically updated user {user_id} fields: {updates}")
                return True
            except Exception as e:
                logger.error(f"Error executing admin update for user {user_id}: {e}")
                return False
            finally:
                conn.close()
                
        return await asyncio.to_thread(_query)

    async def transfer_rps_money(self, winner_id: int, loser_id: int, bet_amount: int, profit: int) -> bool:
        """
        Atomically transfers the bet money between players for Rock-Paper-Scissors, 
        accounting for system commission.
        """
        def _query():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                # Fetch loser's current balance
                cursor.execute("SELECT money FROM users WHERE user_id = ?", (loser_id,))
                loser_row = cursor.fetchone()
                if not loser_row or loser_row[0] < bet_amount:
                    return False
                    
                # Fetch winner's current balance
                cursor.execute("SELECT money FROM users WHERE user_id = ?", (winner_id,))
                winner_row = cursor.fetchone()
                if not winner_row:
                    return False
                    
                # Execute transaction
                new_loser_money = loser_row[0] - bet_amount
                new_winner_money = winner_row[0] + profit
                
                cursor.execute("UPDATE users SET money = ? WHERE user_id = ?", (new_loser_money, loser_id))
                cursor.execute("UPDATE users SET money = ? WHERE user_id = ?", (new_winner_money, winner_id))
                conn.commit()
                logger.info(f"RPS Transfer Success: Winner {winner_id} (+{profit}), Loser {loser_id} (-{bet_amount})")
                return True
            except Exception as e:
                logger.error(f"Error in transfer_rps_money transaction: {e}")
                conn.rollback()
                return False
            finally:
                conn.close()
        return await asyncio.to_thread(_query)

    async def update_begging_time(self, user_id: int, timestamp_str: str) -> bool:
        """Updates last_begging timestamp string for a user."""
        def _query():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET last_begging = ? WHERE user_id = ?", (timestamp_str, user_id))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Error updating begging time for user {user_id}: {e}")
                return False
            finally:
                conn.close()
        return await asyncio.to_thread(_query)

    async def update_teaching_time(self, user_id: int, timestamp_str: str) -> bool:
        """Updates last_teaching timestamp string for a user."""
        def _query():
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.cursor()
                cursor.execute("UPDATE users SET last_teaching = ? WHERE user_id = ?", (timestamp_str, user_id))
                conn.commit()
                return True
            except Exception as e:
                logger.error(f"Error updating teaching time for user {user_id}: {e}")
                return False
            finally:
                conn.close()
        return await asyncio.to_thread(_query)

