import os, time, json
from typing import Dict, Any, Optional
from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
import requests

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")          # export OPENAI_API_KEY=sk-...
SHARED_SECRET  = os.getenv("SHARED_SECRET","Alpha-987654")

app = FastAPI(title="AlphaSignal Relay", version="1.0.0")

DB: Dict[str, Dict[str, Any]] = {}  # stockage en mémoire

class Ingest(BaseModel):
    pair: str
    timeframe: str
    price: float
    RSI: float
    MACD: float
    MACD_signal: float
    ATR: float
    ts: int

class Analyze(BaseModel):
    pair: str
    timeframe: str
    setups_requested: int = 1

@app.get("/status")
def status():
    return {"ok": True, "keys": list(DB.keys()), "count": len(DB)}

@app.post("/ingest")
def ingest(payload: Ingest, x_secret: Optional[str] = Header(None)):
    if x_secret != SHARED_SECRET:
        raise HTTPException(status_code=401, detail="bad secret")
    key = f"{payload.pair}:{payload.timeframe}".upper()
    item = payload.dict()
    item["ingested_at"] = int(time.time())
    DB[key] = item
    return {"ok": True, "stored": key}

SYSTEM_INSTRUCTIONS = """Tu es un générateur de SETUPS SMC/ICT.
Réponds UNIQUEMENT en JSON valide.
Format:
{
  "pair": "<PAIR>",
  "timeframe": "<TF>",
  "setups": [ { "setup_number": 1, "trade_type": "BUY/SELL", "entry_range": "LOW-HIGH", "stop_loss": number, "take_profit": number, "confidence": 90, "analysis": "..." } ]
}
"""

def call_openai(prompt: str) -> Dict[str, Any]:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}
    body = {
        "model": "gpt-4.1",
        "temperature": 0.1,
        "max_tokens": 1000,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_INSTRUCTIONS},
            {"role": "user",   "content": prompt}
        ]
    }
    r = requests.post(url, headers=headers, json=body, timeout=30)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"OpenAI error {r.status_code}: {r.text[:200]}")
    data = r.json()
    return json.loads(data["choices"][0]["message"]["content"])

@app.post("/analyze")
def analyze(req: Analyze, x_secret: Optional[str] = Header(None)):
    if x_secret != SHARED_SECRET:
        raise HTTPException(status_code=401, detail="bad secret")
    key = f"{req.pair}:{req.timeframe}".upper()
    snap = DB.get(key)
    if not snap:
        raise HTTPException(status_code=404, detail="no_data_for " + key)
    prompt = f"PAIR: {req.pair}\nTIMEFRAME: {req.timeframe}\nDATA: {json.dumps(snap)}"
    return call_openai(prompt)
