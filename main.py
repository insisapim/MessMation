from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

app.mount(
    "/web",
    StaticFiles(directory=WEB_DIR),
    name="web",
)

@app.get("/")
def home():
    return FileResponse(WEB_DIR / "index.html")