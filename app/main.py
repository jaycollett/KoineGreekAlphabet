"""Main FastAPI application for Greek Alphabet Mastery."""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.routers import user, quiz

app = FastAPI(
    title="Greek Alphabet Mastery",
    description="Mobile-first adaptive quiz app to master the Greek alphabet",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Set up templates
templates = Jinja2Templates(directory="app/templates")

# Include routers
app.include_router(user.router)
app.include_router(quiz.router)


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the main application page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/quiz", response_class=HTMLResponse)
async def quiz_page(request: Request):
    """Serve the quiz page."""
    return templates.TemplateResponse("quiz.html", {"request": request})


@app.get("/summary", response_class=HTMLResponse)
async def summary_page(request: Request):
    """Serve the quiz summary page."""
    return templates.TemplateResponse("summary.html", {"request": request})


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
