import os
import tempfile

from fastapi import FastAPI, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from scripts.parse_index_excel import run_pipeline

app = FastAPI(title="Predator Uploader")

@app.get("/", response_class=HTMLResponse)
def home():
    return """<html><body><h2>Upload Excel</h2>
    <form action="/upload" method="post" enctype="multipart/form-data">
    <input name="file" type="file" accept=".xlsx,.xls"/><button>Upload & Process</button>
    </form></body></html>"""

@app.post("/upload")
async def upload(file: UploadFile):
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        tmp.write(await file.read()); p = tmp.name
    try:
        result = run_pipeline(
            input_path=p,
            db=os.getenv("DB_URL"), opensearch=os.getenv("OPENSEARCH_URL"),
            qdrant=os.getenv("QDRANT_URL"), minio=os.getenv("MINIO_URL"), bucket="raw",
            embed_model=os.getenv("EMBED_MODEL","nomic-embed-text"),
            embed_batch=int(os.getenv("EMBED_BATCH","64")), dry_run=False, verbose=True
        )
        return JSONResponse({"status":"ok","result":result})
    except Exception as e:
        return JSONResponse({"status":"error","error":str(e)}, status_code=500)
