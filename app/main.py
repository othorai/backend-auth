#services/backend_auth/main.py
from fastapi import FastAPI, HTTPException, Depends, Request, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
import logging
from fastapi.openapi.utils import get_openapi
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.openapi.models import OAuthFlows, OAuthFlowPassword
import httpx
from app.utils.auth import get_current_user, create_access_token, verify_password, get_password_hash
from app.utils.database import get_db
from sqlalchemy.orm import Session
from urllib.parse import unquote
from app.models.models import User, Organization, InteractionHistory, LikedPost, Article, user_organizations
from app.schemas.schemas import (
    UserCreate, User as UserSchema, Token, ChatHistoryResponse,
    Organization as OrganizationSchema, EmailRequest, UserResponse, LikedPostResponse
)
from datetime import datetime, timedelta
from sqlalchemy import insert
from app.services.email_service import generate_verification_token, send_verification_email, send_welcome_email
from app.schemas.schemas import EmailVerificationRequest, ResendVerificationRequest
import os
from typing import Dict, Optional, List, Any
from pydantic import BaseModel
import logging
import uuid
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from app.schemas.schemas import UserRole


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
app = FastAPI(
    title="API Gateway",
    description="API Gateway for microservices",
    docs_url="/docs"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
# Route prefixes and their corresponding services
ROUTE_SERVICES = {
    'narrative': os.getenv('NARRATIVE_SERVICE_URL', 'http://narrative:8000'),
    'api/v1': os.getenv('ORGANIZATIONS_SERVICE_URL', 'http://organizations:8000'),
    'metrics': os.getenv('METRICS_SERVICE_URL', 'http://metrics:8000'),
    'chatbot': os.getenv('CHATBOT_SERVICE_URL', 'http://chatbot:8000'),
    'data-source': os.getenv('DATA_SOURCE_SERVICE_URL', 'http://narrative:8000'),
    'metric-discovery': os.getenv('METRIC_DISCOVERY_SERVICE_URL', 'http://metric-discovery:8000')
}

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="authorization/login",
    scheme_name="OAuth2PasswordBearer"
)

class Visualization(BaseModel):
    type: str
    axis_label: str
    value_format: Dict[str, Any]
    show_points: bool
    stack_type: Optional[str] = None
    show_labels: bool

class GraphData(BaseModel):
    current: float
    previous: float
    change: float
    change_percentage: float
    visualization: Optional[Visualization] = None

class NewsArticle(BaseModel):
    id: str
    title: str
    content: str
    category: str
    time_period: str
    context: Optional[str] = None
    graph_data: Dict[str, GraphData]
    
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="API Gateway",
        version="1.0.0",
        description="API Gateway with OAuth2 password flow authentication",
        routes=app.routes,
    )

    # Security scheme for OAuth2 password flow
    openapi_schema["components"]["securitySchemes"] = {
        "OAuth2PasswordBearer": {
            "type": "oauth2",
            "flows": {
                "password": {
                    "tokenUrl": "authorization/login",
                    "scopes": {}  # Add scopes if needed
                }
            }
        }
    }

    # Add security requirement to all endpoints
    if "security" not in openapi_schema:
        openapi_schema["security"] = []
        
    openapi_schema["security"].append(
        {"OAuth2PasswordBearer": []}
    )

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Validate configuration on startup
@app.on_event("startup")
async def validate_config():
    """Validate configuration on startup"""
    missing_services = [
        service for service, url in ROUTE_SERVICES.items()
        if not url
    ]
    
    if missing_services:
        logger.warning(f"Missing service URLs for: {', '.join(missing_services)}")
        
    logger.info("Service URLs configuration:")
    for service, url in ROUTE_SERVICES.items():
        logger.info(f"{service}: {url or 'NOT CONFIGURED'}")

@app.get("/debug/config")
async def debug_config(current_user: Dict = Depends(get_current_user)):
    """Debug endpoint for configuration status"""
    if not current_user["user"].is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
        
    dotenv_file = os.path.join(os.getcwd(), ".env")
    env_file_exists = os.path.exists(dotenv_file)
    
    return {
        "env_file": {
            "exists": env_file_exists,
            "path": dotenv_file if env_file_exists else None
        },
        "environment_variables": {
            "NARRATIVE_SERVICE_URL": os.getenv('NARRATIVE_SERVICE_URL'),
            "ORGANIZATIONS_SERVICE_URL": os.getenv('ORGANIZATIONS_SERVICE_URL'),
            "METRICS_SERVICE_URL": os.getenv('METRICS_SERVICE_URL'),
            "CHATBOT_SERVICE_URL": os.getenv('CHATBOT_SERVICE_URL'),
            "DATA_SOURCE_SERVICE_URL": os.getenv('DATA_SOURCE_SERVICE_URL'),
            "METRIC_DISCOVERY_SERVICE_URL": os.getenv('METRIC_DISCOVERY_SERVICE_URL')
        },
        "route_services": ROUTE_SERVICES,
        "working_directory": os.getcwd()
    }

@app.get("/debug/services")
async def debug_services(current_user: Dict = Depends(get_current_user)):
    """Debug endpoint for service status"""
    if not current_user["user"].is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
        
    service_status = {}
    for service_name, service_url in ROUTE_SERVICES.items():
        try:
            if service_url:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    try:
                        response = await client.get(f"{service_url}/health")
                        is_healthy = response.status_code == 200
                    except Exception as e:
                        logger.error(f"Health check failed for {service_name}: {str(e)}")
                        is_healthy = False
            else:
                is_healthy = False
                
            service_status[service_name] = {
                "url": service_url,
                "configured": bool(service_url),
                "healthy": is_healthy,
                "error": None if is_healthy else "Service not reachable"
            }
        except Exception as e:
            service_status[service_name] = {
                "url": service_url,
                "configured": bool(service_url),
                "healthy": False,
                "error": str(e)
            }
    
    return {
        "services": service_status,
        "user_context": {
            "user_id": current_user["user"].id,
            "role": current_user["user"].role,
            "org_id": current_user["current_org_id"]
        }
    }

# Add health check endpoint directly to gateway
@app.get("/health")
async def gateway_health():
    """Gateway health check endpoint"""
    return {
        "status": "healthy",
        "service": "gateway",
        "timestamp": datetime.utcnow().isoformat()
    }

def get_full_data_access():
    return "all_departments,all_locations,all_products,financial_data,customer_data,marketing_data,sales_data,employee_data,historical_data,forecasts,system_config,audit_logs"

@app.post("/authorization/signup", response_model=UserSchema)
async def signup(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    username_exists = db.query(User).filter(User.username == user.username).first()
    if username_exists:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    hashed_password = get_password_hash(user.password)
    
    # Determine data access
    if user.data_access is None or user.data_access.lower() in ["full", "all", "everything"]:
        data_access = get_full_data_access()
    else:
        data_access = user.data_access
    
    # Check if organization exists, if not, create it
    org = db.query(Organization).filter(Organization.name == "Wayne Enterprise").first()
    if not org:
        org = Organization(name="Wayne Enterprise")
        db.add(org)
        db.commit()
        db.refresh(org)
    
    token = generate_verification_token()
    
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password,
        role=user.role,
        data_access=data_access,
        is_active=True,
        is_admin=user.role.lower() in ["admin", "ceo"],
        is_verified=True,
        verification_token=token,
        verification_token_expires=datetime.utcnow() + timedelta(hours=24)
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    
    
    # Insert into the association table with role='member'
    db.execute(
        insert(user_organizations).values(
            user_id=db_user.id,
            organization_id=org.id,
            role="member"
        )
    )
    db.commit()
    
    return db_user


@app.post("/authorization/verify-email", include_in_schema=True)
async def verify_email(
    verification_data: EmailVerificationRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.verification_token == verification_data.token,
        User.verification_token_expires > datetime.utcnow()
    ).first()
    
    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired verification token"
        )
    
    if user.is_verified:
        return {"message": "Email already verified"}
    
    user.is_verified = True
    user.verification_token = None
    user.verification_token_expires = None
    db.commit()
    
    # Send welcome email after verification
    if send_welcome_email(user.email):
        return {"message": "Email verified successfully"}
    else:
        # Still return success even if welcome email fails
        logger.error(f"Failed to send welcome email to {user.email}")
        return {"message": "Email verified successfully but failed to send welcome email"}

@app.post("/authorization/resend-verification")
async def resend_verification(
    email_data: ResendVerificationRequest,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email_data.email).first()
    
    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found"
        )
    
    if user.is_verified:
        return {"message": "Email already verified"}
    
    # Generate new verification token
    token = generate_verification_token()
    user.verification_token = token
    user.verification_token_expires = datetime.utcnow() + timedelta(hours=24)
    db.commit()
    
    # Send verification email
    send_verification_email(user.email, token, FRONTEND_URL)
    
    return {"message": "Verification email sent"}

@app.post("/authorization/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please verify your email before logging in",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user's organizations
    if not user.organizations:
        raise HTTPException(status_code=400, detail="User is not associated with any organization")
    
    # For simplicity, we're using the first organization. In a real-world scenario,
    # you might want to let the user choose which organization to log into
    
    access_token = create_access_token(
        data={"sub": user.email, "org_id": user.organizations[0].id if user.organizations else None}
    )
    return {"access_token": access_token, "token_type": "bearer"}

@app.get("/authorization/me", response_model=UserSchema)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    return current_user["user"]

@app.get("/authorization/user/organizations", response_model=List[OrganizationSchema])
async def get_user_organizations(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    user = current_user["user"]
    return user.organizations

@app.post("/authorization/switch-organization/{org_id}", response_model=Token)
async def switch_organization(
    org_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user = current_user["user"]
    org = db.query(Organization).filter(Organization.id == org_id).first()
    
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    if org not in user.organizations:
        raise HTTPException(status_code=403, detail=f"User is not a member of organization {org_id}")
    
    access_token = create_access_token(data={"sub": user.email, "org_id": org_id})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/authorization/user/{user_id}/add-organization/{org_id}")
async def add_user_to_organization(
    user_id: int,
    org_id: int,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if not current_user["user"].is_admin:
        raise HTTPException(status_code=403, detail="Only admins can add users to organizations")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    if org not in user.organizations:
        user.organizations.append(org)
        db.commit()
        return {"message": f"User {user.username} added to organization {org.name}"}
    else:
        return {"message": f"User {user.username} is already a member of organization {org.name}"}

@app.get("/authorization/chat-history/{session_id}", response_model=List[ChatHistoryResponse])
async def get_chat_history(
    session_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    chat_history = db.query(InteractionHistory).filter(
        InteractionHistory.user_id == current_user["user"].id,
        InteractionHistory.session_id == session_id
    ).order_by(InteractionHistory.timestamp).all()

    return [
        ChatHistoryResponse(
            question=interaction.question,
            answer=interaction.answer,
            timestamp=interaction.timestamp
        ) for interaction in chat_history
    ]

@app.post("/authorization/like/{article_id}", response_model=LikedPostResponse)
async def like_post(
    article_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    article = db.query(Article).filter(Article.id == article_id).first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    try:
        liked_post = LikedPost(user_id=current_user["user"].id, article_id=article_id)
        db.add(liked_post)
        db.commit()
        db.refresh(liked_post)
        return LikedPostResponse(message="Post liked successfully", liked=True)
    except IntegrityError:
        db.rollback()
        return LikedPostResponse(message="Post already liked", liked=True)

@app.delete("/authorization/unlike/{article_id}", response_model=LikedPostResponse)
async def unlike_post(
    article_id: uuid.UUID,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    liked_post = db.query(LikedPost).filter(
        LikedPost.user_id == current_user["user"].id,
        LikedPost.article_id == article_id
    ).first()

    if not liked_post:
        return LikedPostResponse(message="Post was not liked", liked=False)

    db.delete(liked_post)
    db.commit()
    return LikedPostResponse(message="Post unliked successfully", liked=False)

@app.get("/authorization/org_role/{org_id}", response_model=UserRole)
async def get_user_org_role(
    org_id: int,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the current user's role in a specific organization.
    Returns 404 if user is not a member of the organization.
    """
    # Access the user object from the dictionary
    user = current_user["user"]
    role = user.get_org_role(org_id, db)
    
    if role is None:
        raise HTTPException(
            status_code=404,
            detail="User is not a member of this organization"
        )
    
    return UserRole(
        organization_id=org_id,
        role=role
    )

@app.get("/authorization/liked-posts", response_model=List[NewsArticle])
async def get_liked_posts(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all liked posts with full article data."""
    try:
        # Get liked posts with article data in a single query using join
        liked_articles = db.query(Article).join(
            LikedPost, 
            LikedPost.article_id == Article.id
        ).filter(
            LikedPost.user_id == current_user["user"].id,
            Article.organization_id == current_user["current_org_id"]
        ).all()

        # Convert to NewsArticle format
        articles = []
        for article in liked_articles:
            # Convert stored graph data to proper format
            graph_data = {}
            if article.graph_data:
                for metric_name, data in article.graph_data.items():
                    visualization = None
                    if 'visualization' in data:
                        visualization = Visualization(
                            type=data['visualization'].get('type', 'line'),
                            axis_label=data['visualization'].get('axis_label', 'Value'),
                            value_format=data['visualization'].get('value_format', {}),
                            show_points=data['visualization'].get('show_points', True),
                            stack_type=data['visualization'].get('stack_type'),
                            show_labels=data['visualization'].get('show_labels', True)
                        )

                    graph_data[metric_name] = GraphData(
                        current=float(data.get('current', 0)),
                        previous=float(data.get('previous', 0)),
                        change=float(data.get('change', 0)),
                        change_percentage=float(data.get('change_percentage', 0)),
                        visualization=visualization
                    )

            articles.append(NewsArticle(
                id=str(article.id),
                title=article.title,
                content=article.content,
                category=article.category,
                time_period=article.time_period,
                graph_data=graph_data
            ))

        return articles

    except Exception as e:
        logger.error(f"Error fetching liked posts: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error fetching liked posts: {str(e)}"
        )

@app.post("/authorization/find-by-email", response_model=UserResponse)
async def find_user_by_email(
    email_data: EmailRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    if not current_user["user"].is_admin:
        raise HTTPException(status_code=403, detail="Only admins can look up users")
    
    user = db.query(User).filter(User.email == email_data.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return user
    
async def check_service_health(service_url: str) -> bool:
    """Check if a service is reachable"""
    if not service_url:
        return False
        
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{service_url}/health", timeout=5.0)
            return response.status_code == 200
    except Exception as e:
        logger.error(f"Health check failed for {service_url}: {str(e)}")
        return False
    
async def forward_request(
    request: Request,
    service_url: str,
    path: str,
    current_user: Optional[Dict] = None,
    method: Optional[str] = None
):
    """Forward request to microservice with enhanced path handling"""
    try:
        request_method = method or request.method
        
        # Normalize service URL and path
        service_url = service_url.rstrip('/')
        path = path if path.startswith('/') else f'/{path}'
        
        full_url = f"{service_url}{path}"
        logger.info(f"Forwarding {request_method} request to: {full_url}")
        
        # Get request body only for methods that should have one
        body = await request.body() if request_method in ['POST', 'PUT', 'PATCH'] else None
        
        # Prepare headers with user context
        headers = dict(request.headers)
        headers.pop('host', None)
        headers.pop('content-length', None)
        
        if current_user:
            headers.update({
                'X-User-ID': str(current_user['user'].id),
                'X-Organization-ID': str(current_user['current_org_id']),
                'X-User-Role': current_user['user'].role,
                'X-User-Data-Access': current_user['user'].data_access or ''
            })
            logger.debug(f"Request headers: {headers}")
        
        # Special handling for health check
        if path.lower() == '/health':
            request_method = 'GET'
        
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            try:
                logger.debug(f"Making request: {request_method} {full_url}")
                logger.debug(f"Query params: {request.query_params}")
                
                response = await client.request(
                    method=request_method,
                    url=full_url,
                    content=body,
                    headers=headers,
                    params=request.query_params
                )
                
                logger.info(f"Service response status: {response.status_code}")
                logger.debug(f"Response headers: {response.headers}")
                
                # Check if response is PDF
                content_type = response.headers.get('content-type', '')
                if 'application/pdf' in content_type:
                    return Response(
                        content=response.content,
                        status_code=response.status_code,
                        media_type='application/pdf',
                        headers={
                            'Content-Type': 'application/pdf',
                            'Content-Disposition': response.headers.get('content-disposition', 'attachment; filename="document.pdf"')
                        }
                    )
                
                # Handle other responses as JSON
                return JSONResponse(
                    content=response.json() if response.text else {},
                    status_code=response.status_code,
                    headers={
                        k: v for k, v in response.headers.items()
                        if k.lower() not in ('content-length', 'transfer-encoding')
                    }
                )
                
            except httpx.RequestError as e:
                logger.error(f"Request to service failed: {str(e)}")
                raise HTTPException(
                    status_code=503,
                    detail=f"Service unavailable: {str(e)}"
                )
            
    except Exception as e:
        logger.exception(f"Error in forward_request: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=str(e))

async def get_service_url(prefix: str) -> str:
    """Get service URL and validate prefix"""
    service_url = ROUTE_SERVICES.get(prefix)
    if not service_url:
        available_services = list(ROUTE_SERVICES.keys())
        logger.error(f"Service not found for prefix '{prefix}'. Available: {available_services}")
        raise HTTPException(
            status_code=404,
            detail=f"Service '{prefix}' not found. Available services: {available_services}"
        )
    return service_url

@app.get(
    "/{prefix}/{path:path}",
    summary="Gateway router for GET requests",
    description="Routes GET requests to appropriate microservices"
)
async def gateway_router_get(
    prefix: str,
    path: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Gateway router for GET requests with enhanced path handling"""
    try:
        # Handle different URL encoding scenarios
        decoded_prefix = unquote(prefix).replace('%2F', '/')
        decoded_path = unquote(path).replace('%2F', '/')
        
        combined_prefix = None
        path_segments = decoded_path.split('/')
        if path_segments:
            combined_prefix = f"{decoded_prefix}/{path_segments[0]}"
            
        # First try the combined prefix, then fall back to original prefix
        service_url = (
            ROUTE_SERVICES.get(combined_prefix) or 
            ROUTE_SERVICES.get(decoded_prefix) or 
            ROUTE_SERVICES.get(decoded_prefix.lower())
        )
        
        if not service_url:
            available_services = list(ROUTE_SERVICES.keys())
            raise HTTPException(
                status_code=404,
                detail=f"Service '{decoded_prefix}' not found. Available services: {available_services}"
            )
        
        # Adjust the forward path based on whether we used the combined prefix
        if combined_prefix and service_url == ROUTE_SERVICES.get(combined_prefix):
            # Remove the first path segment since it's part of the prefix
            forward_path = '/' + '/'.join(path_segments[1:])
        else:
            forward_path = '/' + decoded_path
            
        # Clean and normalize the path
        forward_path = forward_path.rstrip('/')
        if not forward_path:
            forward_path = '/'
        
        return await forward_request(
            request=request,
            service_url=service_url,
            path=forward_path,
            current_user=current_user,
            method="GET"  # Explicitly set method
        )
        
    except Exception as e:
        logger.exception(f"Error in GET router: {str(e)}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Gateway GET error: {str(e)}")

@app.post("/{prefix}/{path:path}")
async def gateway_router_post(
    prefix: str,
    path: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Gateway router for POST requests"""
    try:
        decoded_prefix = unquote(prefix).replace('%2F', '/')
        decoded_path = unquote(path).replace('%2F', '/')
        
        # Try to find service URL directly (this will handle hyphenated names)
        service_url = ROUTE_SERVICES.get(decoded_prefix)
        
        # If no direct match, then try the api/v1 special case
        if not service_url and decoded_prefix == "api" and decoded_path.startswith("v1/"):
            service_url = ROUTE_SERVICES.get("api/v1")
            forward_path = decoded_path[3:]  # Remove "v1/"
        else:
            forward_path = decoded_path

        if not service_url:
            available_services = list(ROUTE_SERVICES.keys())
            raise HTTPException(
                status_code=404,
                detail=f"Service not found. Available services: {available_services}"
            )

        return await forward_request(
            request=request,
            service_url=service_url,
            path=forward_path,
            current_user=current_user,
            method="POST"  # Explicitly set method
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Gateway POST error: {str(e)}")

@app.put("/{prefix}/{path:path}")
async def gateway_router_put(
    prefix: str,
    path: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Gateway router for PUT requests"""
    try:
        decoded_prefix = unquote(prefix).replace('%2F', '/')
        decoded_path = unquote(path).replace('%2F', '/')
        
        # Try to find service URL
        service_url = ROUTE_SERVICES.get(decoded_prefix)

        # If no direct match, then try the api/v1 special case
        if not service_url and decoded_prefix == "api" and decoded_path.startswith("v1/"):
            service_url = ROUTE_SERVICES.get("api/v1")
            forward_path = decoded_path[3:]  # Remove "v1/"
        else:
            forward_path = decoded_path
            
        if decoded_prefix == "api" and decoded_path.startswith("v1/"):
            forward_path = decoded_path[3:]  # Remove "v1/"

        return await forward_request(
            request=request,
            service_url=service_url,
            path=forward_path,
            current_user=current_user,
            method="PUT"  # Explicitly set method
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Gateway PUT error: {str(e)}")

@app.delete("/{prefix}/{path:path}")
async def gateway_router_delete(
    prefix: str,
    path: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Gateway router for DELETE requests"""
    try:
        decoded_prefix = unquote(prefix).replace('%2F', '/')
        decoded_path = unquote(path).replace('%2F', '/')
        
        # Try to find service URL directly (this will handle hyphenated names)
        service_url = ROUTE_SERVICES.get(decoded_prefix)
        
        # If no direct match, then try the api/v1 special case
        if not service_url and decoded_prefix == "api" and decoded_path.startswith("v1/"):
            service_url = ROUTE_SERVICES.get("api/v1")
            forward_path = decoded_path[3:]  # Remove "v1/"
        else:
            forward_path = decoded_path

        if not service_url:
            available_services = list(ROUTE_SERVICES.keys())
            raise HTTPException(
                status_code=404,
                detail=f"Service not found. Available services: {available_services}"
            )

        return await forward_request(
            request=request,
            service_url=service_url,
            path=forward_path,
            current_user=current_user,
            method="DELETE"  # Explicitly set method
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Gateway POST error: {str(e)}")

@app.patch("/{prefix}/{path:path}")
async def gateway_router_patch(
    prefix: str,
    path: str,
    request: Request,
    current_user: Dict = Depends(get_current_user)
):
    """Gateway router for PATCH requests"""
    try:
        decoded_prefix = unquote(prefix).replace('%2F', '/')
        decoded_path = unquote(path).replace('%2F', '/')
        
        # Try to find service URL
        service_url = None
        if decoded_prefix == "api" and decoded_path.startswith("v1/"):
            service_url = ROUTE_SERVICES.get("api/v1")
        
        if not service_url:
            available_services = list(ROUTE_SERVICES.keys())
            raise HTTPException(
                status_code=404,
                detail=f"Service not found. Available services: {available_services}"
            )

        # Adjust forward path
        forward_path = decoded_path
        if decoded_prefix == "api" and decoded_path.startswith("v1/"):
            forward_path = decoded_path[3:]  # Remove "v1/"

        return await forward_request(
            request=request,
            service_url=service_url,
            path=forward_path,
            current_user=current_user,
            method="PATCH"  # Explicitly set method
        )

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Gateway PATCH error: {str(e)}")

# Add health check endpoint directly to gateway
@app.get("/health")
async def gateway_health():
    """Gateway health check endpoint"""
    return {
        "status": "healthy",
        "service": "gateway",
        "timestamp": datetime.utcnow().isoformat()
    }