import asyncio
import sqlite3
from sqlalchemy.ext.asyncio import create_async_engine
from config.settings import settings
from db.models import Base, InterviewSession

async def recreate_db():
    """Force recreate all tables from fresh models."""
    db_path = settings.sqlite_db_path
    
    # Delete file if exists
    import os
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"✅ Deleted old {db_path}")
    
    # Create engine
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )
    
    # Drop all tables (safety)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        print("✅ Dropped all existing tables")
    
    # Recreate all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        print("✅ Created all tables from model definitions")
    
    # Verify
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(interview_sessions);")
    columns = cursor.fetchall()
    
    print()
    print("📊 New schema verification:")
    for col in columns:
        col_id, name, type_, notnull, default, pk = col
        marker = "✓ PK" if pk else ""
        print(f"   {name:30} {type_:10} {marker}".strip())
    
    has_counter = any(col[1] == 'different_question_count' for col in columns)
    print()
    if has_counter:
        print("✅ SUCCESS: different_question_count field created!")
    else:
        print("❌ FAILED: different_question_count not found!")
    
    conn.close()

asyncio.run(recreate_db())
