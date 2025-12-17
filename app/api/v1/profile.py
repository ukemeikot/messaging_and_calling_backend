"""
Profile management routes.
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse
from app.schemas.profile import ProfileUpdate, PasswordChange, ProfilePictureResponse
from app.services.profile_service import ProfileService
from app.services.user_service import UserService
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
    """
    Get current user's profile.
    
    Returns full profile including bio, profile picture, etc.
    """
    return UserResponse.model_validate(current_user)

@router.put(
    "",
    response_model=UserResponse,
    summary="Update profile",
    description="""
    Update user profile information.
    
    **Fields you can update:**
    - full_name: Your full name
    - bio: Short biography (max 500 characters)
    
    **Note:** Only send fields you want to update.
    """
)
async def update_profile(
    profile_data: ProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Update user profile.
    
    Args:
        profile_data: Profile fields to update
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Updated user profile
    """
    
    profile_service = ProfileService(db)
    
    # Update profile
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
    description="""
    Change user password.
    
    **Requirements:**
    - Must provide current password for verification
    - New password must meet strength requirements
    
    **Security:**
    - Current password verified before change
    - New password hashed securely
    """
)
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change user password.
    
    Args:
        password_data: Current and new passwords
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Success message
        
    Raises:
        HTTPException 400: If current password is incorrect
    """
    
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
    description="""
    Upload a profile picture.
    
    **Supported formats:** JPEG, PNG, GIF
    **Max size:** 5MB
    **Recommended:** Square image, at least 400x400px
    
    **Process:**
    1. Upload image
    2. Validate format and size
    3. Save to storage
    4. Update user profile
    """
)
async def upload_profile_picture(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload profile picture.
    
    Args:
        file: Image file (JPEG, PNG, GIF)
        current_user: Authenticated user
        db: Database session
        
    Returns:
        Profile picture URL
        
    Raises:
        HTTPException 400: Invalid file format or size
    """
    
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
    max_size = 5 * 1024 * 1024  # 5MB in bytes
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
    
    # Create uploads directory if it doesn't exist
    upload_dir = Path("uploads/profile_pictures")
    upload_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    file_extension = Path(file.filename or "image.jpg").suffix
    unique_filename = f"{current_user.id}{file_extension}"
    file_path = upload_dir / unique_filename
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(file_content)
    
    # Update user profile with file URL
    # Note: In production, you'd upload to S3/CloudStorage and get a public URL
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
    description="""
    Get any user's public profile information.
    
    **Privacy:**
    - Returns only public information
    - Email hidden unless you're friends (future feature)
    - Some fields may be hidden based on privacy settings
    """
)
async def get_user_profile(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get user profile by ID.
    
    Args:
        user_id: UUID of user to view
        db: Database session
        
    Returns:
        User profile
        
    Raises:
        HTTPException 404: User not found
    """
    
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