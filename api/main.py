"""
Predator Analytics FastAPI Backend
"""

import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import jwt
import prometheus_client
import redis
import structlog
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from prometheus_client import Counter, Gauge, Histogram
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.database import get_db

# Database imports
from api.models import Record

# Configure structured logging
logger = structlog.get_logger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    "http_requests_total", "Total HTTP requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds", "HTTP request latency", ["method", "endpoint"]
)
ACTIVE_CONNECTIONS = Gauge("active_connections", "Number of active connections")
CUSTOMS_RECORDS_TOTAL = Counter("customs_records_total", "Total customs records processed")
SEARCH_QUERIES_TOTAL = Counter("search_queries_total", "Total search queries")
ANALYTICS_QUERIES_TOTAL = Counter("analytics_queries_total", "Total analytics queries")


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting Predator Analytics API")
    ACTIVE_CONNECTIONS.set(0)

    yield

    # Shutdown
    logger.info("Shutting down Predator Analytics API")


# Create FastAPI app
app = FastAPI(
    title="Predator Analytics API",
    description="Autonomous Multi-Agent Analytics Platform",
    version="13.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Security
security = HTTPBearer()

# Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])  # Configure for production

# Rate limiting storage
redis_client = redis.Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

# Keycloak configuration
KEYCLOAK_CONFIG = {
    "url": os.getenv("KEYCLOAK_URL", "http://localhost:8080"),
    "realm": os.getenv("KEYCLOAK_REALM", "predator"),
    "client_id": os.getenv("KEYCLOAK_CLIENT_ID", "predator-api"),
    "client_secret": os.getenv("KEYCLOAK_CLIENT_SECRET"),
    "public_key": os.getenv("KEYCLOAK_PUBLIC_KEY"),
}


# Pydantic models
class User(BaseModel):
    id: str
    username: str
    email: str
    roles: list[str] = []
    groups: list[str] = []


class CustomsRecord(BaseModel):
    id: str | None = None
    hs_code: str = Field(..., min_length=4, max_length=10)
    company_name: str
    edrpou: str = Field(..., min_length=8, max_length=10)
    amount: float = Field(..., gt=0)
    date: datetime
    country_code: str = Field(..., min_length=2, max_length=3)
    customs_office: str
    op_hash: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    filters: dict[str, Any] = {}
    limit: int = Field(10, ge=1, le=1000)
    offset: int = Field(0, ge=0)


class AnalyticsRequest(BaseModel):
    query: str
    time_range: dict[str, datetime] = {}
    group_by: list[str] = []
    metrics: list[str] = []


class UploadResponse(BaseModel):
    records_processed: int
    records_failed: int
    duplicates_found: int
    processing_time: float


# Dependencies
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """Get current authenticated user"""
    try:
        token = credentials.credentials

        # Decode JWT token
        public_key = KEYCLOAK_CONFIG.get("public_key")
        if not public_key:
            raise HTTPException(status_code=500, detail="Auth misconfigured: missing public key")
        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=KEYCLOAK_CONFIG["client_id"],
        )

        return User(
            id=payload.get("sub"),
            username=payload.get("preferred_username"),
            email=payload.get("email"),
            roles=payload.get("realm_access", {}).get("roles", []),
            groups=payload.get("groups", []),
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def require_role(required_role: str):
    """Dependency to require specific role"""

    def role_checker(user: User = Depends(get_current_user)):
        if required_role not in user.roles:
            raise HTTPException(status_code=403, detail=f"Role '{required_role}' required")
        return user

    return role_checker


async def rate_limit(request: Request, max_requests: int = 100, window_seconds: int = 60):
    """Rate limiting middleware"""
    client_ip = request.client.host
    key = f"rate_limit:{client_ip}"

    # Check current requests in window
    current = redis_client.get(key)
    if current and int(current) >= max_requests:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    # Increment counter
    pipe = redis_client.pipeline()
    pipe.incr(key)
    pipe.expire(key, window_seconds)
    pipe.execute()


@app.middleware("http")
async def core_middleware(request: Request, call_next):
    """Combined middleware: rate limiting + metrics."""
    start_time = datetime.now()
    ACTIVE_CONNECTIONS.inc()

    # Rate limit (skip for metrics & health)
    if request.url.path not in ["/metrics", "/health"]:
        await rate_limit(request)

    try:
        response = await call_next(request)
        REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, status=response.status_code).inc()
        REQUEST_LATENCY.labels(method=request.method, endpoint=request.url.path).observe((datetime.now() - start_time).total_seconds())
        return response
    finally:
        ACTIVE_CONNECTIONS.dec()


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat(), "version": "13.0.0"}


# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(media_type="text/plain", content=prometheus_client.generate_latest())


# Authentication endpoints
@app.post("/auth/login")
async def login():
    """Login endpoint - redirects to Keycloak"""
    # This would redirect to Keycloak login


@app.post("/auth/logout")
async def logout(user: User = Depends(get_current_user)):
    """Logout endpoint"""
    return {"message": "Logged out successfully"}


# Customs data endpoints
@app.post("/api/v1/customs/upload", response_model=UploadResponse)
async def upload_customs_data(
    file: UploadFile,
    dataset_name: str = None,
    user: User = Depends(require_role("data_uploader")),
    db: Session = Depends(get_db),
):
    """
    Upload customs data file and automatically index across all databases
    
    Databases indexed:
    - PostgreSQL: structured data storage with deduplication
    - OpenSearch: full-text search (company names, HS codes, offices)
    - Qdrant: vector similarity search (embeddings)
    - Neo4j: graph relationships (companies, products, countries)
    - Redis: statistics caching (HS codes, companies, countries)
    
    Returns:
        UploadResponse with processing statistics
    """
    import time
    from api.upload_service import MultiDatabaseUploadService
    
    start_time = time.time()
    temp_path = None
    
    try:
        logger.info(f"📤 Upload started by user '{user.username}': {file.filename}")
        
        # Auto-generate dataset name if not provided
        if not dataset_name:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            base_name = file.filename.rsplit('.', 1)[0]
            dataset_name = f"customs_{timestamp}_{base_name}"
        
        # Save temp file
        temp_path = f"/tmp/upload_{datetime.now().timestamp()}_{file.filename}"
        content = await file.read()
        with open(temp_path, "wb") as f:
            f.write(content)
        
        logger.info(f"✅ Saved temp file: {temp_path}")
        
        # Process upload using Multi-Database service
        upload_service = MultiDatabaseUploadService()
        result = await upload_service.process_upload(
            file_path=temp_path,
            filename=file.filename,
            dataset_name=dataset_name,
            owner=user.username,
            db=db
        )
        
        # Cleanup temp file
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)
            logger.info(f"🗑️ Cleaned up temp file")
        
        # Update Prometheus metrics
        CUSTOMS_RECORDS_TOTAL.inc(result["records_processed"])
        
        processing_time = time.time() - start_time
        
        # Log summary
        logger.info(
            "Upload completed for user '%s', file '%s', dataset '%s'. "
            "Processed: %d, Duplicates: %d, Failed: %d, Time: %.2fs",
            user.username,
            file.filename,
            dataset_name,
            result["records_processed"],
            result["duplicates"],
            result["failed"],
            processing_time,
        )
        
        if result["errors"]:
            logger.warning("⚠️ Errors during indexing: %s", result["errors"])

        return UploadResponse(
            records_processed=result["records_processed"],
            records_failed=result["failed"],
            duplicates_found=result["duplicates"],
            processing_time=processing_time,
        )

    except Exception as e:
        logger.error("❌ Upload failed: %s", e, exc_info=True)

        # Cleanup on error
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

        raise HTTPException(
            status_code=500,
            detail=f"Upload failed: {str(e)}"
        )


@app.post("/api/v1/customs/search")
async def search_customs_data(
    request: SearchRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Search customs data"""
    try:
        import time

        start_time = time.time()

        # Build query
        query = db.query(Record)

        # Apply filters
        if request.filters:
            if "hs_code" in request.filters:
                query = query.filter(Record.hs_code == request.filters["hs_code"])
            if "company_name" in request.filters:
                query = query.filter(
                    Record.company_name.ilike(f"%{request.filters['company_name']}%")
                )
            if "edrpou" in request.filters:
                query = query.filter(Record.edrpou == request.filters["edrpou"])
            if "country_code" in request.filters:
                query = query.filter(Record.country_code == request.filters["country_code"])
            if "date_from" in request.filters:
                query = query.filter(Record.date >= request.filters["date_from"])
            if "date_to" in request.filters:
                query = query.filter(Record.date <= request.filters["date_to"])
            if "amount_min" in request.filters:
                query = query.filter(Record.amount >= request.filters["amount_min"])
            if "amount_max" in request.filters:
                query = query.filter(Record.amount <= request.filters["amount_max"])

        # Text search (basic implementation)
        if request.query:
            search_term = f"%{request.query}%"
            query = query.filter(
                (Record.company_name.ilike(search_term))
                | (Record.customs_office.ilike(search_term))
                | (Record.hs_code.ilike(search_term))
            )

        # Get total count
        total = query.count()

        # Apply pagination
        results = query.offset(request.offset).limit(request.limit).all()

        # Format results
        records = []
        for record in results:
            records.append(
                {
                    "id": str(record.id),
                    "hs_code": record.hs_code,
                    "company_name": record.company_name,
                    "edrpou": record.edrpou,
                    "amount": float(record.amount) if record.amount else None,
                    "date": record.date.isoformat() if record.date else None,
                    "country_code": record.country_code,
                    "customs_office": record.customs_office,
                    "attrs": record.attrs,
                }
            )

        search_time = time.time() - start_time
        SEARCH_QUERIES_TOTAL.inc()

        return {
            "results": records,
            "total": total,
            "took": round(search_time, 3),
            "query": request.query,
            "filters": request.filters,
        }

    except Exception as e:
        logger.error("Search failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")


@app.post("/api/v1/customs/analytics")
async def analytics_customs_data(
    request: AnalyticsRequest, user: User = Depends(require_role("analyst"))
):
    """Analytics on customs data"""
    try:
        ANALYTICS_QUERIES_TOTAL.inc()

        # This would use the miner agent for analysis
        return {"insights": [], "charts": {}, "metrics": {}}

    except Exception as e:
        logger.error("Analytics failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Analytics failed")


# Agent endpoints
@app.post("/api/v1/agents/query")
async def query_agents(query: str, user: User = Depends(get_current_user)):
    """Query MAS agents"""
    try:
        # This would orchestrate agents via LangGraph
        return {"response": "Agent response", "confidence": 0.95, "sources": []}

    except Exception as e:
        logger.error("Agent query failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Agent query failed")


@app.get("/api/v1/agents/status")
async def get_agents_status(user: User = Depends(require_role("admin"))):
    """Get agents status"""
    return {
        "agents": {"retriever": "active", "miner": "active", "arbiter": "active"},
        "last_heartbeat": datetime.now().isoformat(),
    }


# Personalization endpoints
@app.get("/api/v1/personalization/feed")
async def get_personalized_feed(user: User = Depends(get_current_user)):
    """Get personalized daily newspaper"""
    try:
        # This would generate personalized insights
        return {"feed": [], "generated_at": datetime.now().isoformat()}

    except Exception as e:
        logger.error("Feed generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Feed generation failed")


# Admin endpoints
@app.get("/api/v1/admin/metrics")
async def get_system_metrics(user: User = Depends(require_role("admin"))):
    """Get system metrics"""
    return {
        "cdc_lag": 0.5,
        "active_connections": ACTIVE_CONNECTIONS._value.get(),
        "total_records": CUSTOMS_RECORDS_TOTAL._value.get(),
        "uptime": "1d 2h 30m",
    }


@app.post("/api/v1/admin/cache/clear")
async def clear_cache(user: User = Depends(require_role("admin"))):
    """Clear Redis cache"""
    try:
        redis_client.flushall()
        return {"message": "Cache cleared"}

    except Exception as e:
        logger.error("Cache clear failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail="Cache clear failed")


# WebSocket endpoints for real-time updates
# (Would be added with fastapi.WebSocket)


# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    REQUEST_COUNT.labels(
        method=request.method, endpoint=request.url.path, status=exc.status_code
    ).inc()

    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s", exc, exc_info=True)
    REQUEST_COUNT.labels(method=request.method, endpoint=request.url.path, status=500).inc()

    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,
        log_level="info",
    )
