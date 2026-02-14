"""
Run the admin panel server.
"""

import sys
import os
import asyncio

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import database initialization
from bot.database.database import init_db, close_db

async def startup():
    """Initialize database on startup."""
    await init_db()
    print("✅ Database initialized")

async def shutdown():
    """Close database on shutdown."""
    await close_db()
    print("✅ Database closed")

if __name__ == "__main__":
    import uvicorn
    from admin.admin_app import app
    
    # Initialize database
    asyncio.run(startup())
    
    print("🚀 Starting admin panel on http://localhost:8000")
    print("📊 Access the admin dashboard at http://localhost:8000")
    
    try:
        uvicorn.run(
            "admin.admin_app:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n⏹️  Shutting down admin panel...")
    finally:
        asyncio.run(shutdown())
