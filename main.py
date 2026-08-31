import os

from fastapi import FastAPI, HTTPException, status, Header
from pydantic import BaseModel
from dotenv import load_dotenv
from supabase import create_client, Client


# -------------------------
# Environment configuration
# -------------------------

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing from .env")

if not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_KEY is missing from .env")


# -------------------------
# Supabase client
# -------------------------

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)


# -------------------------
# FastAPI application
# -------------------------

app = FastAPI(
    title="Task API",
    description="CRUD API with Supabase authentication.",
    version="2.0"
)


# -------------------------
# Request models
# -------------------------

class SignupRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


# -------------------------
# Health check
# -------------------------

@app.get(
    "/health",
    summary="Check API health",
    description="Returns the current health status of the API."
)
def health_check():
    return {
        "status": "ok",
        "supabase": "configured"
    }


# -------------------------
# Root endpoint
# -------------------------

@app.get(
    "/",
    summary="Get API information",
    description="Returns information about the API."
)
def read_root():
    return {
        "name": "Task API",
        "version": "2.0",
        "endpoints": [
            "/health",
            "/auth/signup",
            "/auth/login",
            "/auth/logout",
            "/public/info",
            "/protected/profile",
            "/protected/dashboard"
        ]
    }


# -------------------------
# POST /auth/signup
# -------------------------

@app.post(
    "/auth/signup",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    description="Creates a new user account using Supabase Auth."
)
def signup(request: SignupRequest):

    if not request.email or not request.email.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )

    if not request.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required"
        )

    try:
        response = supabase.auth.sign_up({
            "email": request.email.strip(),
            "password": request.password
        })

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create account"
        )

    if response.user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to create account"
        )

    return {
        "user": response.user
    }


# -------------------------
# POST /auth/login
# -------------------------

@app.post(
    "/auth/login",
    summary="Log in",
    description="Authenticates a user and returns access and refresh tokens."
)
def login(request: LoginRequest):

    if not request.email or not request.email.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is required"
        )

    if not request.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password is required"
        )

    try:
        response = supabase.auth.sign_in_with_password({
            "email": request.email.strip(),
            "password": request.password
        })

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login credentials"
        )

    if response.session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid login credentials"
        )

    return {
        "access_token": response.session.access_token,
        "refresh_token": response.session.refresh_token
    }


# -------------------------
# GET /public/info
# -------------------------

@app.get(
    "/public/info",
    summary="Get public information",
    description="Public endpoint that does not require authentication."
)
def public_info():
    return {
        "message": "Welcome stranger! This info is public."
    }


# -------------------------
# GET /protected/profile
# -------------------------

@app.get(
    "/protected/profile",
    summary="Get protected profile",
    description="Protected endpoint that requires an access token."
)
def protected_profile(authorization: str | None = Header(default=None)):

    # Check whether the Authorization header exists
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required"
        )

    # Check that the header uses the Bearer format
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required"
        )

    # Extract the token
    token = authorization[7:].strip()

    # Check that a token was actually provided
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required"
        )


    return {
        "message": "You provided an access token.",
        "token_received": True
    }