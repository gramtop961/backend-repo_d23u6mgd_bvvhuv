import os
from typing import List, Optional
import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Database helpers (optional but used when available)
try:
    from database import db, create_document, get_documents
except Exception:
    db = None
    def create_document(*args, **kwargs):
        return None
    def get_documents(*args, **kwargs):
        return []

app = FastAPI(title="Plant AI Guardian Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PLANT_API_BASE = os.getenv("PLANT_API_BASE", "https://my-plant-ai.com")


# ===== Pydantic Models =====
class PredictRequest(BaseModel):
    image: str = Field(..., description="Base64-encoded image string")

class PredictResponse(BaseModel):
    disease: str
    confidence: float
    organ: Optional[str] = None
    severity: Optional[str] = None

class TreatmentItem(BaseModel):
    symptoms: Optional[str] = None
    organic: Optional[str] = None
    chemical: Optional[str] = None
    prevention: Optional[str] = None

class ProductItem(BaseModel):
    name: str
    price: Optional[float] = None
    url: Optional[str] = None
    image: Optional[str] = None

class TutorialItem(BaseModel):
    title: str
    videoId: Optional[str] = None
    thumbnail: Optional[str] = None
    url: Optional[str] = None

class AnalyzeResponse(BaseModel):
    result: PredictResponse
    treatments: List[TreatmentItem] = []
    products: List[ProductItem] = []
    tutorials: List[TutorialItem] = []


# ===== Helpers =====
def external_predict(image_base64: str) -> PredictResponse:
    url = f"{PLANT_API_BASE}/predict"
    try:
        r = requests.post(url, json={"image": image_base64}, timeout=20)
        r.raise_for_status()
        data = r.json()
        disease = data.get("disease", "Unknown")
        confidence = float(data.get("confidence", 0.5))
    except Exception:
        # Fallback mock for development
        disease = "Leaf Blight"
        confidence = 0.87
    # Simple heuristics for demo
    organ = "leaf"
    severity = "high" if confidence > 0.85 else ("medium" if confidence > 0.6 else "low")
    return PredictResponse(disease=disease, confidence=confidence, organ=organ, severity=severity)


def external_treatments(disease: str) -> List[TreatmentItem]:
    url = f"{PLANT_API_BASE}/treatments"
    try:
        r = requests.get(url, params={"disease": disease}, timeout=15)
        r.raise_for_status()
        items = r.json()
        out = []
        if isinstance(items, list):
            for it in items:
                out.append(TreatmentItem(
                    symptoms=it.get("symptoms"),
                    organic=it.get("organic"),
                    chemical=it.get("chemical"),
                    prevention=it.get("prevention") or it.get("preventive")
                ))
        else:
            out.append(TreatmentItem(symptoms="Spots and lesions on leaves",
                                     organic="Neem oil spray weekly",
                                     chemical="Copper-based fungicide as directed",
                                     prevention="Ensure proper spacing and airflow"))
        return out
    except Exception:
        return [TreatmentItem(symptoms="Spots and lesions on leaves",
                              organic="Neem oil spray weekly",
                              chemical="Copper-based fungicide as directed",
                              prevention="Ensure proper spacing and airflow")]


def external_products(disease: str) -> List[ProductItem]:
    url = f"{PLANT_API_BASE}/products"
    try:
        r = requests.get(url, params={"disease": disease}, timeout=15)
        r.raise_for_status()
        items = r.json()
        out: List[ProductItem] = []
        if isinstance(items, list):
            for it in items:
                price = None
                try:
                    price = float(it.get("price")) if it.get("price") is not None else None
                except Exception:
                    price = None
                out.append(ProductItem(name=it.get("name", "Product"), price=price, url=it.get("url"), image=it.get("image")))
            return out
    except Exception:
        pass
    return [
        ProductItem(name="Bio Neem Oil", price=12.99, url="https://example.com/neem", image="https://images.unsplash.com/photo-1524594081293-190a2fe0baae?q=80&w=400"),
        ProductItem(name="Copper Fungicide", price=18.49, url="https://example.com/copper", image="https://images.unsplash.com/photo-1542291026-7eec264c27ff?q=80&w=400"),
    ]


def external_tutorials(disease: str) -> List[TutorialItem]:
    url = f"{PLANT_API_BASE}/tutorials"
    try:
        r = requests.get(url, params={"disease": disease}, timeout=15)
        r.raise_for_status()
        items = r.json()
        out: List[TutorialItem] = []
        if isinstance(items, list):
            for it in items:
                out.append(TutorialItem(title=it.get("title", "Tutorial"), videoId=it.get("videoId"), thumbnail=it.get("thumbnail"), url=it.get("url")))
            return out
    except Exception:
        pass
    # Mock tutorials
    return [
        TutorialItem(title=f"How to treat {disease}", videoId="dQw4w9WgXcQ", thumbnail="https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg", url=f"https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        TutorialItem(title=f"Preventing {disease} in your garden", videoId="9bZkp7q19f0", thumbnail="https://img.youtube.com/vi/9bZkp7q19f0/hqdefault.jpg", url=f"https://www.youtube.com/watch?v=9bZkp7q19f0"),
    ]


# ===== Routes =====
@app.get("/")
def root():
    return {"status": "ok", "service": "Plant AI Guardian Backend"}


@app.post("/api/predict", response_model=PredictResponse)
def predict(req: PredictRequest):
    return external_predict(req.image)


@app.get("/api/treatments", response_model=List[TreatmentItem])
def treatments(disease: str):
    return external_treatments(disease)


@app.get("/api/products", response_model=List[ProductItem])
def products(disease: str):
    return external_products(disease)


@app.get("/api/tutorials", response_model=List[TutorialItem])
def tutorials(disease: str):
    return external_tutorials(disease)


@app.post("/api/analyze", response_model=AnalyzeResponse)
def analyze(req: PredictRequest):
    result = external_predict(req.image)
    treatments = external_treatments(result.disease)
    products = external_products(result.disease)
    tutorials = external_tutorials(result.disease)

    # persist minimal analysis record if DB available
    try:
        if db is not None:
            create_document("analysis", {
                "disease": result.disease,
                "confidence": result.confidence,
                "organ": result.organ,
                "severity": result.severity,
            })
    except Exception:
        pass

    return AnalyzeResponse(result=result, treatments=treatments, products=products, tutorials=tutorials)


@app.get("/api/recent")
def recent(limit: int = 8):
    # Return latest analyses if DB available, else mocked data
    if db is not None:
        try:
            docs = list(db["analysis"].find({}).sort("created_at", -1).limit(limit))
            out = []
            for d in docs:
                out.append({
                    "disease": d.get("disease"),
                    "confidence": d.get("confidence"),
                    "severity": d.get("severity"),
                })
            return out
        except Exception:
            pass
    # Fallback mock
    return [
        {"disease": "Leaf Blight", "confidence": 0.87, "severity": "high"},
        {"disease": "Powdery Mildew", "confidence": 0.76, "severity": "medium"},
        {"disease": "Rust", "confidence": 0.63, "severity": "medium"},
        {"disease": "Healthy", "confidence": 0.94, "severity": "low"},
    ]


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
