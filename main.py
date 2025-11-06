import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from bson import ObjectId
from datetime import datetime

from database import db, create_document, get_documents
from schemas import Post

app = FastAPI(title="The Foreign Desk API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "The Foreign Desk backend is running"}

@app.get("/test")
def test_database():
    status = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "collections": []
    }
    try:
        if db is not None:
            status["database"] = "✅ Connected"
            try:
                status["collections"] = db.list_collection_names()[:10]
            except Exception as e:
                status["database"] = f"⚠️ Connected but error: {str(e)[:80]}"
        else:
            status["database"] = "❌ Not Configured"
    except Exception as e:
        status["database"] = f"❌ Error: {str(e)[:80]}"
    return status

# Helper: convert ObjectId to string

def _normalize(doc):
    if not doc:
        return doc
    d = dict(doc)
    if "_id" in d:
        d["id"] = str(d.pop("_id"))
    # convert datetime to isoformat
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d

# Posts Endpoints

@app.get("/api/posts", response_model=List[Post])
def list_posts(q: Optional[str] = Query(None, description="Search query"), limit: int = 50):
    filter_dict = {}
    if q:
        # Basic case-insensitive regex search across fields
        regex = {"$regex": q, "$options": "i"}
        filter_dict = {"$or": [
            {"title": regex},
            {"region": regex},
            {"excerpt": regex},
            {"tags": regex},
        ]}
    docs = get_documents("post", filter_dict, limit)
    # Map to Post-like dicts (ensure required fields exist)
    normalized = []
    for doc in docs:
        nd = _normalize(doc)
        # tolerate missing optional fields
        normalized.append({
            "title": nd.get("title", ""),
            "region": nd.get("region", ""),
            "excerpt": nd.get("excerpt", ""),
            "date": nd.get("date"),
            "tags": nd.get("tags", []),
            "content": nd.get("content", []),
        })
    return normalized

@app.post("/api/posts")
def create_post(post: Post):
    try:
        inserted_id = create_document("post", post)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/posts/{post_id}")
def get_post(post_id: str):
    try:
        if not ObjectId.is_valid(post_id):
            raise HTTPException(status_code=400, detail="Invalid id")
        doc = db["post"].find_one({"_id": ObjectId(post_id)})
        if not doc:
            raise HTTPException(status_code=404, detail="Not found")
        return _normalize(doc)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/posts/{post_id}")
def delete_post(post_id: str):
    try:
        if not ObjectId.is_valid(post_id):
            raise HTTPException(status_code=400, detail="Invalid id")
        res = db["post"].delete_one({"_id": ObjectId(post_id)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Not found")
        return {"status": "deleted"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
