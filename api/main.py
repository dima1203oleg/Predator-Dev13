"""
Predator Analytics FastAPI Backend
"""
import os
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn
import jwt
import redis
import prometheus_client
from prometheus_client import Counter, Histogram, Gauge
import structlog

# Database imports
from api.models import Record, Dataset
from api.database import get_db
from sqlalchemy.orm import Session

# Configure structured logging
logger = structlog.get_logger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter('http_requests_total', 'Total HTTP requests', ['method', 'endpoint', 'status'])
REQUEST_LATENCY = Histogram('http_request_duration_seconds', 'HTTP request latency', ['method', 'endpoint'])
ACTIVE_CONNECTIONS = Gauge('active_connections', 'Number of active connections')
CUSTOMS_RECORDS_TOTAL = Counter('customs_records_total', 'Total customs records processed')
SEARCH_QUERIES_TOTAL = Counter('search_queries_total', 'Total search queries')
ANALYTICS_QUERIES_TOTAL = Counter('analytics_queries_total', 'Total analytics queries')

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
    openapi_url="/openapi.json"
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

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure for production
)

# Rate limiting storage
redis_client = redis.Redis.from_url(os.getenv('REDIS_URL', 'redis://localhost:6379/0'))

# Keycloak configuration
KEYCLOAK_CONFIG = {
    "url": os.getenv("KEYCLOAK_URL", "http://localhost:8080"),
    "realm": os.getenv("KEYCLOAK_REALM", "predator"),
    "client_id": os.getenv("KEYCLOAK_CLIENT_ID", "predator-api"),
    "client_secret": os.getenv("KEYCLOAK_CLIENT_SECRET"),
    "public_key": os.getenv("KEYCLOAK_PUBLIC_KEY")
}

# Pydantic models
class User(BaseModel):
    id: str
    username: str
    email: str
    roles: List[str] = []
    groups: List[str] = []

class CustomsRecord(BaseModel):
    id: Optional[str] = None
    hs_code: str = Field(..., min_length=4, max_length=10)
    company_name: str
    edrpou: str = Field(..., min_length=8, max_length=10)
    amount: float = Field(..., gt=0)
    date: datetime
    country_code: str = Field(..., min_length=2, max_length=3)
    customs_office: str
    op_hash: Optional[str] = None

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    filters: Dict[str, Any] = {}
    limit: int = Field(10, ge=1, le=1000)
    offset: int = Field(0, ge=0)

class AnalyticsRequest(BaseModel):
    query: str
    time_range: Dict[str, datetime] = {}
    group_by: List[str] = []
    metrics: List[str] = []

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
        payload = jwt.decode(
            token,
            KEYCLOAK_CONFIG["public_key"],
            algorithms=["RS256"],
            audience=KEYCLOAK_CONFIG["client_id"]
        )

        return User(
            id=payload.get("sub"),
            username=payload.get("preferred_username"),
            email=payload.get("email"),
            roles=payload.get("realm_access", {}).get("roles", []),
            groups=payload.get("groups", [])
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def require_role(required_role: str):
    """Dependency to require specific role"""
    def role_checker(user: User = Depends(get_current_user)):
        if required_role not in user.roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{required_role}' required"
            )
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

# Middleware for metrics
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    start_time = datetime.now()

    # Track active connections
    ACTIVE_CONNECTIONS.inc()

    try:
        response = await call_next(request)

        # Record metrics
        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()

        REQUEST_LATENCY.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe((datetime.now() - start_time).total_seconds())

        return response

    finally:
        ACTIVE_CONNECTIONS.dec()

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "version": "13.0.0"
    }

# Metrics endpoint
@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    return Response(
        media_type="text/plain",
        content=prometheus_client.generate_latest()
    )

# Authentication endpoints
@app.post("/auth/login")
async def login():
    """Login endpoint - redirects to Keycloak"""
    # This would redirect to Keycloak login
    pass

@app.post("/auth/logout")
async def logout(user: User = Depends(get_current_user)):
    """Logout endpoint"""
    return {"message": "Logged out successfully"}

# Customs data endpoints
@app.post("/api/v1/customs/upload", response_model=UploadResponse)
async def upload_customs_data(
    file: UploadFile,
    dataset_id: str,
    user: User = Depends(require_role("data_uploader")),
    db: Session = Depends(get_db)
):
    """Upload customs data file"""
    try:
        from parsers.excel_parser import ExcelParser
        import hashlib
        
        # Get dataset
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            raise HTTPException(status_code=404, detail="Dataset not found")
        
        # Parse file
        parser = ExcelParser()
        content = await file.read()
        
        # Save temp file
        temp_path = f"/tmp/{file.filename}"
        with open(temp_path, "wb") as f:
            f.write(content)
        
        # Parse data
        parse_result = parser.parse(temp_path)
        records_data = parser.convert_to_records(parse_result, file.filename)
        
        processed = 0
        failed = 0
        duplicates = 0
        
        for record_data in records_data:
            try:
                # Check for duplicates
                existing = db.query(Record).filter(
                    Record.op_hash == record_data.get("op_hash")
                ).first()
                
                if existing:
                    duplicates += 1
                    continue
                
                # Create record
                record = Record(
                    dataset_id=dataset_id,
                    pk=record_data["pk"],
                    op_hash=record_data["op_hash"],
                    hs_code=record_data.get("hs_code"),
                    date=record_data.get("date"),
                    amount=record_data.get("amount"),
                    qty=record_data.get("qty"),
                    country_code=record_data.get("country_code"),
                    edrpou=record_data.get("edrpou"),
                    company_name=record_data.get("company_name"),
                    customs_office=record_data.get("customs_office"),
                    attrs=record_data,
                    source_file=file.filename,
                    source_row=record_data.get("source_row")
                )
                
                db.add(record)
                processed += 1
                
            except Exception as e:
                logger.warning(f"Record processing failed: {e}")
                failed += 1
        
        db.commit()
        CUSTOMS_RECORDS_TOTAL.inc(processed)
        
        # Cleanup
        os.remove(temp_path)
        
        return UploadResponse(
            records_processed=processed,
            records_failed=failed,
            duplicates_found=duplicates,
            processing_time=0.0  # Would measure actual time
        )

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail="Upload failed")

@app.post("/api/v1/customs/search")
async def search_customs_data(
    request: SearchRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Search customs data"""
    try:
        from datetime import datetime
        import time
        
        start_time = time.time()
        
        # Build query
        query = db.query(Record)
        
        # Apply filters
        if request.filters:
            if "hs_code" in request.filters:
                query = query.filter(Record.hs_code == request.filters["hs_code"])
            if "company_name" in request.filters:
                query = query.filter(Record.company_name.ilike(f"%{request.filters['company_name']}%"))
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
                (Record.company_name.ilike(search_term)) |
                (Record.customs_office.ilike(search_term)) |
                (Record.hs_code.ilike(search_term))
            )
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        results = query.offset(request.offset).limit(request.limit).all()
        
        # Format results
        records = []
        for record in results:
            records.append({
                "id": str(record.id),
                "hs_code": record.hs_code,
                "company_name": record.company_name,
                "edrpou": record.edrpou,
                "amount": float(record.amount) if record.amount else None,
                "date": record.date.isoformat() if record.date else None,
                "country_code": record.country_code,
                "customs_office": record.customs_office,
                "attrs": record.attrs
            })
        
        search_time = time.time() - start_time
        SEARCH_QUERIES_TOTAL.inc()
        
        return {
            "results": records,
            "total": total,
            "took": round(search_time, 3),
            "query": request.query,
            "filters": request.filters
        }

    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")

@app.post("/api/v1/customs/analytics")
async def analytics_customs_data(
    request: AnalyticsRequest,
    user: User = Depends(require_role("analyst"))
):
    """Analytics on customs data"""
    try:
        ANALYTICS_QUERIES_TOTAL.inc()

        # This would use the miner agent for analysis
        return {
            "insights": [],
            "charts": {},
            "metrics": {}
        }

    except Exception as e:
        logger.error(f"Analytics failed: {e}")
        raise HTTPException(status_code=500, detail="Analytics failed")

# Agent endpoints
@app.post("/api/v1/agents/query")
async def query_agents(
    query: str,
    user: User = Depends(get_current_user)
):
    """Query MAS agents"""
    try:
        # This would orchestrate agents via LangGraph
        return {
            "response": "Agent response",
            "confidence": 0.95,
            "sources": []
        }

    except Exception as e:
        logger.error(f"Agent query failed: {e}")
        raise HTTPException(status_code=500, detail="Agent query failed")

@app.get("/api/v1/agents/status")
async def get_agents_status(
    user: User = Depends(require_role("admin"))
):
    """Get agents status"""
    return {
        "agents": {
            "retriever": "active",
            "miner": "active",
            "arbiter": "active"
        },
        "last_heartbeat": datetime.now().isoformat()
    }

# Personalization endpoints
@app.get("/api/v1/personalization/feed")
async def get_personalized_feed(
    user: User = Depends(get_current_user)
):
    """Get personalized daily newspaper"""
    try:
        # This would generate personalized insights
        return {
            "feed": [],
            "generated_at": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Feed generation failed: {e}")
        raise HTTPException(status_code=500, detail="Feed generation failed")

# Admin endpoints
@app.get("/api/v1/admin/metrics")
async def get_system_metrics(
    user: User = Depends(require_role("admin"))
):
    """Get system metrics"""
    return {
        "cdc_lag": 0.5,
        "active_connections": ACTIVE_CONNECTIONS._value.get(),
        "total_records": CUSTOMS_RECORDS_TOTAL._value.get(),
        "uptime": "1d 2h 30m"
    }

@app.post("/api/v1/admin/cache/clear")
async def clear_cache(
    user: User = Depends(require_role("admin"))
):
    """Clear Redis cache"""
    try:
        redis_client.flushall()
        return {"message": "Cache cleared"}

    except Exception as e:
        logger.error(f"Cache clear failed: {e}")
        raise HTTPException(status_code=500, detail="Cache clear failed")

# WebSocket endpoints for real-time updates
# (Would be added with fastapi.WebSocket)

# Error handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=exc.status_code
    ).inc()

    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {exc}")
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        status=500
    ).inc()

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("API_PORT", "8000")),
        reload=True,
        log_level="info"
    )
