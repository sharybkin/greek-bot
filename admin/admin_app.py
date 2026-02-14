"""
FastAPI Admin Panel for Greek Learning Bot.
"""

import os
from typing import List
from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from bot.database.database import get_session
from bot.database.repositories.user_repo import UserRepository
from bot.database.repositories.admin_repo import AdminRepository
from bot.config import config
from bot.utils.logger import logger

app = FastAPI(title="Greek Bot Admin Panel")

# Serve static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)
app.mount("/static", StaticFiles(directory=static_dir), name="static")


class PremiumToggleRequest(BaseModel):
    """Request model for toggling premium status."""
    telegram_id: int
    is_premium: bool


@app.get("/")
async def root():
    """Serve the admin panel HTML."""
    html_path = os.path.join(static_dir, "index.html")
    if os.path.exists(html_path):
        return FileResponse(html_path)
    return {"message": "Admin panel - HTML not found"}


@app.get("/api/users")
async def get_users(session: AsyncSession = Depends(get_session)):
    """
    Get all users with their statistics.
    
    Returns:
        List of users with statistics
    """
    try:
        admin_repo = AdminRepository(session)
        users = await admin_repo.get_all_users_with_stats()
        return {"users": users}
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/statistics")
async def get_statistics(session: AsyncSession = Depends(get_session)):
    """
    Get global statistics.
    
    Returns:
        Global statistics
    """
    try:
        admin_repo = AdminRepository(session)
        stats = await admin_repo.get_global_statistics()
        return stats
    except Exception as e:
        logger.error(f"Error fetching statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/users/premium")
async def toggle_premium(
    request: PremiumToggleRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Toggle premium status for a user.
    
    Args:
        request: Premium toggle request
        
    Returns:
        Success message
    """
    try:
        user_repo = UserRepository(session)
        await user_repo.update_premium_status(request.telegram_id, request.is_premium)
        
        status = "premium" if request.is_premium else "regular"
        logger.info(f"Updated user {request.telegram_id} to {status}")
        
        return {
            "success": True,
            "message": f"User {request.telegram_id} is now {status}"
        }
    except Exception as e:
        logger.error(f"Error toggling premium: {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
