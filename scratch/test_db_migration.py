import os
import json
import sqlite3
import shutil
import asyncio
import logging
import sys

# Add parent directory of 'src' to python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.db_manager import DatabaseManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("test_db_migration")

async def test_migration_and_crud():
    logger.info("Setting up test files...")
    
    # Paths
    sqlite_db_path = "config/game_database.db"
    json_db_path = "config/game_database_test.json"
    
    # Ensure config directory exists
    os.makedirs("config", exist_ok=True)
    
    # 1. Clean up any existing files from previous tests
    for p in [sqlite_db_path, sqlite_db_path + ".bak", json_db_path]:
        if os.path.exists(p):
            if os.path.isdir(p):
                shutil.rmtree(p)
            else:
                os.remove(p)
                
    # 2. Create a dummy SQLite DB with some user data
    logger.info(f"Creating mock SQLite database at {sqlite_db_path}...")
    conn = sqlite3.connect(sqlite_db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE users (
            user_id INTEGER PRIMARY KEY,
            username TEXT NOT NULL,
            money INTEGER DEFAULT 50000,
            items TEXT DEFAULT '[]',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_checkin TEXT,
            checkin_streak INTEGER DEFAULT 0,
            last_begging TEXT,
            last_teaching TEXT
        )
    """)
    
    # Insert two test users
    cursor.execute("""
        INSERT INTO users (user_id, username, money, items, last_checkin, checkin_streak, last_begging, last_teaching)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (111111, "김단또", 75000, '["참치캔", "쥐돌이 장난감"]', "2026-07-10", 3, "2026-07-11 12:00:00", "2026-07-11 13:00:00"))
    
    cursor.execute("""
        INSERT INTO users (user_id, username, money, items, last_checkin, checkin_streak, last_begging, last_teaching)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (222222, "박단또", 120000, '[]', None, 0, None, None))
    
    conn.commit()
    conn.close()
    
    logger.info("Initializing DatabaseManager and trigger automatic migration...")
    # Initialize the DatabaseManager with our test JSON path
    db = DatabaseManager(db_path=json_db_path)
    
    # Assertions
    logger.info("Verifying migration results...")
    assert os.path.exists(json_db_path), "JSON database file should be created!"
    assert os.path.exists(sqlite_db_path + ".bak"), "SQLite database should be backed up as .db.bak!"
    assert not os.path.exists(sqlite_db_path), "Original SQLite database file should be removed/renamed!"
    
    # Read the migrated JSON directly to verify file formatting and data
    with open(json_db_path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    logger.info(f"Migrated JSON data:\n{json.dumps(data, indent=2, ensure_ascii=False)}")
    
    users = data.get("users", {})
    assert "111111" in users, "User 111111 should be migrated!"
    assert "222222" in users, "User 222222 should be migrated!"
    
    # Assert item values are parsed as a native JSON array, not string
    assert isinstance(users["111111"]["items"], list), "Items should be stored as a JSON array!"
    assert "참치캔" in users["111111"]["items"], "Should contain 참치캔!"
    
    logger.info("Verifying DatabaseManager CRUD methods for backward compatibility...")
    
    # Test get_user
    u1 = await db.get_user(111111)
    assert u1 is not None
    assert u1["username"] == "김단또"
    assert u1["money"] == 75000
    # The return format of items should be a JSON string for game command compatibility
    assert isinstance(u1["items"], str)
    assert "참치캔" in u1["items"]
    
    # Test get_user_by_name (fuzzy match)
    u1_fuzzy = await db.get_user_by_name("김단")
    assert u1_fuzzy is not None
    assert u1_fuzzy["user_id"] == 111111
    
    # Test register_user (new user)
    reg_success = await db.register_user(333333, "이단또")
    assert reg_success is True
    u3 = await db.get_user(333333)
    assert u3["money"] == 50000
    assert u3["items"] == "[]"
    
    # Test update_money
    new_bal = await db.update_money(111111, 25000)
    assert new_bal == 100000
    u1_updated = await db.get_user(111111)
    assert u1_updated["money"] == 100000
    
    # Test checkin_user
    # Yesterday checkin was 2026-07-10, let's do today checkin (consecutive checkin)
    checkin_res = await db.checkin_user(111111, today_str="2026-07-11", yesterday_str="2026-07-10")
    assert checkin_res["status"] == "success"
    assert checkin_res["reward"] == 10000
    assert checkin_res["streak"] == 4
    assert checkin_res["money"] == 110000
    
    # Double check-in today should fail
    checkin_res_again = await db.checkin_user(111111, today_str="2026-07-11", yesterday_str="2026-07-10")
    assert checkin_res_again["status"] == "already"
    
    # Test get_db_stats
    stats = await db.get_db_stats()
    assert stats["total_users"] == 3
    # 111111 (110000) + 222222 (120000) + 333333 (50000) = 280000
    assert stats["total_money"] == 280000
    
    # Test get_top_users
    top = await db.get_top_users(limit=2)
    assert len(top) == 2
    assert top[0]["user_id"] == 222222  # Richest (120,000)
    assert top[1]["user_id"] == 111111  # Second richest (110,000)
    
    # Test admin_update_user
    admin_success = await db.admin_update_user(333333, {"money": 999999, "items": '["행운의 네잎클로버"]'})
    assert admin_success is True
    u3_admin = await db.get_user(333333)
    assert u3_admin["money"] == 999999
    assert "행운의 네잎클로버" in u3_admin["items"]
    
    # Verify file formatting on disk is indented and readable
    with open(json_db_path, "r", encoding="utf-8") as f:
        raw_content = f.read()
        logger.info(f"Raw file preview of formatting:\n{raw_content[:400]}...")
        # Check indentation and spacing
        assert "    \"users\": {" in raw_content, "JSON should be pretty-printed with 4 spaces indent!"
        
    logger.info("All tests completed successfully!")
    
    # Clean up test files
    for p in [sqlite_db_path, sqlite_db_path + ".bak", json_db_path]:
        if os.path.exists(p):
            os.remove(p)
            
if __name__ == "__main__":
    asyncio.run(test_migration_and_crud())
