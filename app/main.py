# app/main.py
from fastapi import FastAPI
from pydantic import BaseModel
import os, json

# try to import google genai; optional fallback if not installed/authorized
try:
    import google.genai as genai
    GENAI_AVAILABLE = True
except Exception:
    GENAI_AVAILABLE = False

app = FastAPI(title="LeadScore Lite - Track A")

class Lead(BaseModel):
    name: str | None = None
    email: str | None = None
    company_size: str | None = "small"
    pitch: str | None = ""
    engagement: dict | None = {"email_clicks":0,"page_views":0}
    last_contact_days: int | None = 999

def rule_score(lead: Lead):
    size_map = {"small":0.33,"medium":0.66,"large":1.0}
    company_norm = size_map.get((lead.company_size or "").lower(), 0.33)
    engagement_norm = min(1.0, (lead.engagement.get("email_clicks",0)/10) + (lead.engagement.get("page_views",0)/50))
    recency_norm = max(0, (30 - (lead.last_contact_days or 999))/30)
    w_size, w_eng, w_rec = 0.4, 0.35, 0.25
    score_float = company_norm*w_size + engagement_norm*w_eng + recency_norm*w_rec
    contributions = {
        "company_size": round(company_norm * w_size * 100, 2),
        "engagement": round(engagement_norm * w_eng * 100, 2),
        "recency": round(recency_norm * w_rec * 100, 2)
    }
    return int(round(score_float*100)), contributions

async def call_genai_scoring(lead: Lead):
    # minimal safe call using google-genai SDK (model name configurable)
    if not GENAI_AVAILABLE:
        raise RuntimeError("google-genai SDK not installed")
    client = genai.Client()  # uses ADC or API key if set
    model = os.environ.get("GENAI_MODEL", "text-bison@001")  # default; change per availability
    prompt = (
        "You are a lead-scoring assistant. Given the JSON lead, return JSON: "
        '{"score":<int 0-100>,"reasons":[{"reason":"...","contribution":<int>}]}'
        f"\n\nLead:\n{lead.json()}\n\nReturn only JSON."
    )
    resp = client.generate_text(model=model, prompt=prompt, max_output_tokens=200)
    text = resp.text if hasattr(resp, "text") else str(resp)
    return json.loads(text)

@app.post("/score")
async def score(lead: Lead):
    base_score, contributions = rule_score(lead)
    model_info = {"used_genai": False, "note": None}
    try:
        genai_out = await call_genai_scoring(lead)
        if isinstance(genai_out, dict) and "score" in genai_out:
            model_score = int(genai_out["score"])
            final_score = int(round((base_score + model_score)/2))
            model_info = {"used_genai": True, "genai_score": model_score, "genai_reasons": genai_out.get("reasons")}
            return {"score": final_score, "explanation": {"rule_contributions": contributions, "model": model_info}}
    except Exception as e:
        model_info = {"used_genai": False, "note": str(e)}
    return {"score": base_score, "explanation": {"rule_contributions": contributions, "model": model_info}}