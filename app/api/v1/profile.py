"""
Profile management routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse
from app.schemas.profile import (
    ProfileUpdate, 
    PasswordChange, 
    ProfilePictureResponse,
    DeleteAccountRequest  # Added this import
)
from app.services.profile_service import ProfileService
from app.services.user_service import UserService
from app.core.security import verify_password  # Added this import
import uuid
import os
from pathlib import Path

router = APIRouter(
    prefix="/profile",
    tags=["Profile Management"]
)

@router.get(
    "",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Get the authenticated user's full profile information"
)
async def get_profile(
    current_user: User = Depends(get_current_user)
):
    return UserResponse.model_validate(current_user)

@router.put(
    "",
    response_model=UserResponse,
    summary="Update profile",
    description="Update user profile information."
)
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    profile_service = ProfileService(db)
    
    updated_user = await profile_service.update_profile(
        user=current_user,
        full_name=profile_data.full_name,
        bio=profile_data.bio
    )
    
    return UserResponse.model_validate(updated_user)

@router.post(
    "/password",
    status_code=status.HTTP_200_OK,
    summary="Change password",
    description="Change user password."
)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    profile_service = ProfileService(db)
    
    try:
        await profile_service.change_password(
            user=current_user,
            current_password=password_data.current_password,
            new_password=password_data.new_password
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "password_change_failed",
                "message": str(e)
            }
        )
    
    return {
        "message": "Password changed successfully",
        "note": "Please use your new password for future logins"
    }

@router.post(
    "/picture",
    response_model=ProfilePictureResponse,
    summary="Upload profile picture",
    description="Upload a profile picture."
)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_file_type",
                "message": f"Only JPEG, PNG, and GIF images are allowed. Got: {file.content_type}",
                "allowed_types": allowed_types
            }
        )
    
    # Validate file size (5MB max)
    max_size = 5 * 1024 * 1024
    file_content = await file.read()
    if len(file_content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "file_too_large",
                "message": f"File size exceeds 5MB. Got: {len(file_content) / (1024 * 1024):.2f}MB",
                "max_size_mb": 5
            }
        )
    
    # Create uploads directory
    upload_dir = Path("uploads/profile_pictures")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_extension = Path(file.filename or "image.jpg").suffix
    unique_filename = f"{current_user.id}{file_extension}"
    file_path = upload_dir / unique_filename
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    profile_picture_url = f"/uploads/profile_pictures/{unique_filename}"
    
    profile_service = ProfileService(db)
    await profile_service.update_profile_picture(
        user=current_user,
        picture_url=profile_picture_url
    )
    
    return ProfilePictureResponse(
        message="Profile picture uploaded successfully",
        profile_picture_url=profile_picture_url
    )

@router.get(
    "/{user_id}",
    response_model=UserResponse,
    summary="Get user profile by ID",
    description="Get any user's public profile information."
)
async def get_user_profile(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    user_service = UserService(db)
    user = await user_service.get_user_by_id(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "user_not_found",
                "message": f"User with ID {user_id} not found"
            }
        )
    
    return UserResponse.model_validate(user)

@router.delete(
    "",
    status_code=status.HTTP_200_OK,
    summary="Delete account",
    description="""
    Permanently delete your account.
    
    **Security:**
    - Requires password confirmation
    - This action cannot be undone
    """
)
async def delete_account(
    confirmation: DeleteAccountRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Delete authenticated user account.
    """
    
    # 1. Verify password matches
    if not verify_password(confirmation.password, str(current_user.hashed_password)):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "invalid_password",
                "message": "The password provided is incorrect."
            }
        )
    
    # 2. Delete user
    user_service = UserService(db)
    await user_service.delete_user(current_user)
    
    return {
        "message": "Account deleted successfully",
        "email": current_user.email
    }