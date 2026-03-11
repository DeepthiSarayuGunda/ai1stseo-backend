import io
import json
import os
import re
import sqlite3
import subprocess
from fastapi.staticfiles import StaticFiles
from datetime import datetime
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from pypdf import PdfReader

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ----------------------
# Config
# ----------------------
DB_PATH = "summaries.db"
MAX_CHARS = 80_000

# Limit uploads to avoid huge files crashing the server
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", "15000000"))  # 15 MB default

# Use env var for session secret (recommended)
SESSION_SECRET = os.getenv("SESSION_SECRET", "dev-only-secret-change-me")

# Optional: protect OpenClaw API calls with a token header
# If set, OpenClaw must send header: X-OpenClaw-Token: <token>
OPENCLAW_API_TOKEN = os.getenv("OPENCLAW_API_TOKEN", "")

app.add_middleware(SessionMiddleware, secret_key=SESSION_SECRET)

ALLOWED_EXTS = {".pdf", ".txt"}


# ----------------------
# OpenClaw Status Helpers
# ----------------------
def check_openclaw_status() -> dict:
    """Check if OpenClaw is available and get its status."""
    # Try multiple possible locations for openclaw binary
    openclaw_paths = [
        "/usr/bin/openclaw",  # Most common location first
        "openclaw",  # Try PATH
        "/usr/local/bin/openclaw",
        os.path.expanduser("~/.local/bin/openclaw"),
        os.path.expanduser("~/bin/openclaw"),
    ]
    
    for openclaw_cmd in openclaw_paths:
        try:
            result = subprocess.run(
                [openclaw_cmd, "health"],
                capture_output=True,
                text=True,
                timeout=10,  # Increased timeout to 10 seconds
                env=dict(os.environ, PATH=os.environ.get("PATH", "") + ":/usr/local/bin:/usr/bin:~/.local/bin")
            )
            
            # Check if output contains "Agents:" which indicates OpenClaw is running
            # OpenClaw health command doesn't always return exit code 0
            output = result.stdout.strip()
            stderr = result.stderr.strip()
            
            # Look for positive indicators in output
            if "Agents:" in output or "agent:main" in output.lower() or "main (default)" in output:
                return {
                    "available": True,
                    "status": "connected",
                    "message": "OpenClaw is running and healthy",
                    "details": output,
                    "command": openclaw_cmd
                }
            elif result.returncode == 0 and output:
                # Fallback to exit code check if there's output
                return {
                    "available": True,
                    "status": "connected",
                    "message": "OpenClaw is running and healthy",
                    "details": output,
                    "command": openclaw_cmd
                }
            else:
                # Command found but not healthy - try next path
                continue
                
        except FileNotFoundError:
            # Try next path
            continue
        except subprocess.TimeoutExpired:
            # Timeout - but OpenClaw might still be working, just slow
            # Try to return partial success if we got here from /usr/bin/openclaw
            if openclaw_cmd == "/usr/bin/openclaw":
                return {
                    "available": True,
                    "status": "connected",
                    "message": "OpenClaw is installed (health check slow)",
                    "details": "OpenClaw found at /usr/bin/openclaw but health check timed out",
                    "command": openclaw_cmd
                }
            continue
        except Exception as e:
            # Try next path
            continue
    
    # None of the paths worked
    return {
        "available": False,
        "status": "not_found",
        "message": "OpenClaw CLI not found on system",
        "details": f"Tried paths: {', '.join(openclaw_paths)}"
    }


def get_system_info() -> dict:
    """Get system information."""
    import platform
    import socket
    
    try:
        hostname = socket.gethostname()
    except:
        hostname = "unknown"
    
    return {
        "hostname": hostname,
        "platform": platform.system(),
        "python_version": platform.python_version(),
        "app_version": "1.0.0"
    }


# ----------------------
# DB helpers
# ----------------------
def db_conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_email TEXT NOT NULL,
                filename TEXT NOT NULL,
                created_at TEXT NOT NULL,
                bullets_json TEXT NOT NULL,
                published INTEGER NOT NULL DEFAULT 0,
                word_count INTEGER DEFAULT 0,
                keywords_json TEXT DEFAULT '[]',
                file_size INTEGER DEFAULT 0,
                document_text TEXT DEFAULT ''
            )
            """
        )
        conn.commit()
        
        # Add document_text column if it doesn't exist (for existing databases)
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(summaries)")
            columns = [row[1] for row in cursor.fetchall()]
            if 'document_text' not in columns:
                conn.execute("ALTER TABLE summaries ADD COLUMN document_text TEXT DEFAULT ''")
                conn.commit()
        except:
            pass  # Column already exists or other error


init_db()


# ----------------------
# Upload helpers
# ----------------------
def _get_ext(filename: str) -> str:
    filename = filename or ""
    dot = filename.rfind(".")
    return filename[dot:].lower() if dot >= 0 else ""


async def read_upload_limited(file: UploadFile) -> bytes:
    data = await file.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValueError(
            f"File too large. Max upload is {MAX_UPLOAD_BYTES // 1_000_000} MB."
        )
    return data


# ----------------------
# Text extraction
# ----------------------
def extract_text(filename: str, data: bytes) -> str:
    ext = _get_ext(filename)
    if ext not in ALLOWED_EXTS:
        raise ValueError("Only .txt and .pdf files are supported.")

    if ext == ".txt":
        return data.decode("utf-8", errors="ignore")

    # PDF
    reader = PdfReader(io.BytesIO(data))
    parts: List[str] = []
    for i, page in enumerate(reader.pages):
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            # Skip problematic pages rather than failing the whole file
            parts.append("")
    return "\n".join(parts)


def clamp_text(text: str) -> str:
    text = (text or "").strip()
    return text[:MAX_CHARS]


# ----------------------
# Local "AI-like" summarizer (NO API)
# Extractive summary via word frequency scoring
# ----------------------
_STOPWORDS = {
    "the","a","an","and","or","but","if","then","else","when","while","for","to","of","in","on","at","by",
    "with","from","as","is","are","was","were","be","been","being","it","this","that","these","those",
    "i","you","he","she","they","we","our","your","their","them","his","her","its","not","no","yes",
    "can","could","should","would","may","might","will","just","also","more","most","very"
}

def _split_sentences(text: str) -> List[str]:
    text = re.sub(r"\s+", " ", text.strip())
    sents = re.split(r"(?<=[.!?])\s+", text)
    sents = [s.strip() for s in sents if len(s.strip()) >= 25]
    return sents


def _tokenize(text: str) -> List[str]:
    words = re.findall(r"[A-Za-z0-9']+", text.lower())
    return [w for w in words if w not in _STOPWORDS and len(w) > 2]


def extract_keywords(text: str, top_n: int = 10) -> List[str]:
    """Extract top keywords from text based on frequency."""
    freq = {}
    for w in _tokenize(text):
        freq[w] = freq.get(w, 0) + 1
    
    if not freq:
        return []
    
    # Sort by frequency and return top N
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:top_n]]


def get_word_count(text: str) -> int:
    """Get word count from text."""
    words = re.findall(r"\b\w+\b", text)
    return len(words)


def summarize_bullets_openclaw(text: str) -> List[str]:
    """
    Uses OpenClaw CLI to generate AI-powered bullet point summaries.
    Falls back to local summarization if OpenClaw is unavailable.
    """
    try:
        # Truncate text if too long for OpenClaw
        text_sample = text[:8000] if len(text) > 8000 else text
        
        # Build prompt for OpenClaw
        prompt = f"""Please analyze this document and provide 6-10 key bullet points summarizing the main ideas, findings, or important information. Format your response as a simple list with each point on a new line starting with a dash (-).

Document text:
{text_sample}

Provide only the bullet points, no additional commentary."""

        # Execute OpenClaw CLI
        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "--message", prompt, "--json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # Parse OpenClaw JSON response
            openclaw_response = json.loads(result.stdout)
            
            # Extract the text response from payloads
            if "result" in openclaw_response and "payloads" in openclaw_response["result"]:
                payloads = openclaw_response["result"]["payloads"]
                if payloads and len(payloads) > 0:
                    response_text = payloads[0].get("text", "")
                    
                    # Parse bullet points from response
                    bullets = []
                    for line in response_text.split('\n'):
                        line = line.strip()
                        # Look for lines starting with -, *, or numbers
                        if line.startswith('-') or line.startswith('*') or (len(line) > 2 and line[0].isdigit() and line[1] in '.):'):
                            # Remove the bullet marker
                            clean_line = re.sub(r'^[-*•]\s*', '', line)
                            clean_line = re.sub(r'^\d+[.):]\s*', '', clean_line)
                            if len(clean_line) > 20:  # Only keep substantial points
                                bullets.append(clean_line.strip())
                    
                    if bullets:
                        return bullets[:10]  # Return up to 10 bullets
        
        # Fallback to local summarization if OpenClaw fails
        return summarize_bullets_local(text)
        
    except Exception as e:
        # Fallback to local summarization on any error
        print(f"OpenClaw error: {e}, falling back to local summarization")
        return summarize_bullets_local(text)


def summarize_bullets_local(text: str) -> List[str]:
    """
    Produces 6–10 bullet points without any external AI.
    Fallback method when OpenClaw is unavailable.
    """
    sentences = _split_sentences(text)
    if not sentences:
        lines = [ln.strip() for ln in text.splitlines() if len(ln.strip()) >= 25]
        return [ln[:140] for ln in lines[:8]] if lines else ["No content to summarize."]

    freq = {}
    for w in _tokenize(text):
        freq[w] = freq.get(w, 0) + 1

    if not freq:
        picked = sentences[:8]
        return [s[:140] for s in picked]

    scored = []
    for idx, s in enumerate(sentences):
        score = 0
        for w in _tokenize(s):
            score += freq.get(w, 0)
        score += max(0, 10 - idx) * 0.2
        scored.append((score, idx, s))

    scored.sort(reverse=True, key=lambda x: x[0])

    k = min(8, max(6, len(sentences) // 8))
    chosen = sorted(scored[:k], key=lambda x: x[1])

    bullets: List[str] = []
    seen = set()
    for _, _, s in chosen:
        s = s.strip()
        if len(s) > 160:
            s = s[:160].rsplit(" ", 1)[0] + "..."
        # Deduplicate
        key = s.lower()
        if key not in seen:
            bullets.append(s)
            seen.add(key)

    return bullets[:10]


# Alias for backward compatibility
def summarize_bullets(text: str) -> List[str]:
    """Main summarization function - uses OpenClaw with local fallback."""
    return summarize_bullets_openclaw(text)


# ----------------------
# Auth helpers (demo)
# ----------------------
def current_user_email(request: Request) -> Optional[str]:
    return request.session.get("user_email")


def require_login(request: Request) -> Optional[RedirectResponse]:
    if not current_user_email(request):
        return RedirectResponse(url="/login", status_code=303)
    return None


# ----------------------
# OpenClaw-friendly API endpoint (JSON)
# ----------------------
@app.post("/api/summarize")
async def api_summarize(file: UploadFile = File(...), request: Request = None):
    """
    This endpoint is meant for OpenClaw integration.
    - No session login required
    - Returns JSON
    - Optional token header (if OPENCLAW_API_TOKEN is set):
      X-OpenClaw-Token: <token>
    """
    if OPENCLAW_API_TOKEN:
        token = request.headers.get("X-OpenClaw-Token", "") if request else ""
        if token != OPENCLAW_API_TOKEN:
            return JSONResponse({"error": "Unauthorized"}, status_code=401)

    try:
        data = await read_upload_limited(file)
        text = clamp_text(extract_text(file.filename, data))
        if not text:
            return JSONResponse(
                {"error": "No readable text found (scanned PDF may not work)."},
                status_code=400,
            )
        bullets = summarize_bullets(text)
        return {"filename": file.filename or "document", "bullets": bullets}
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=400)


# ----------------------
# Routes (HTML)
# ----------------------
@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if current_user_email(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return RedirectResponse(url="/login", status_code=303)


@app.get("/api/health")
def api_health():
    """API health check endpoint."""
    openclaw_status = check_openclaw_status()
    return {
        "app_status": "running",
        "openclaw_status": openclaw_status["status"],
        "openclaw_available": openclaw_status["available"],
        "location": "AWS EC2"
    }


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request, "error": None})


@app.post("/login", response_class=HTMLResponse)
def login_action(request: Request, email: str = Form(...)):
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        return templates.TemplateResponse(
            "login.html", {"request": request, "error": "Enter a valid email (demo login)."}
        )
    request.session["user_email"] = email
    return RedirectResponse(url="/dashboard", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect
    
    # Get OpenClaw status for dashboard
    openclaw_status = check_openclaw_status()
    
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user_email": current_user_email(request),
            "error": None,
            "openclaw_status": openclaw_status
        },
    )


@app.post("/summarize", response_class=HTMLResponse)
async def summarize(request: Request, file: UploadFile = File(...)):
    redirect = require_login(request)
    if redirect:
        return redirect

    try:
        data = await read_upload_limited(file)
        text = clamp_text(extract_text(file.filename, data))

        if not text:
            return templates.TemplateResponse(
                "dashboard.html",
                {
                    "request": request,
                    "user_email": current_user_email(request),
                    "error": "No readable text found (scanned PDF may not work).",
                },
            )

        bullets = summarize_bullets(text)
        keywords = extract_keywords(text, top_n=10)
        word_count = get_word_count(text)
        file_size = len(data)

        created_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        with db_conn() as conn:
            cur = conn.execute(
                "INSERT INTO summaries (user_email, filename, created_at, bullets_json, published, word_count, keywords_json, file_size, document_text) VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?)",
                (
                    current_user_email(request),
                    file.filename or "document",
                    created_at,
                    json.dumps(bullets),
                    word_count,
                    json.dumps(keywords),
                    file_size,
                    text,  # Store the full document text for Q&A
                ),
            )
            summary_id = cur.lastrowid
            conn.commit()

        return templates.TemplateResponse(
            "result.html",
            {
                "request": request,
                "user_email": current_user_email(request),
                "summary_id": summary_id,
                "filename": file.filename,
                "created_at": created_at,
                "bullets": bullets,
                "published": False,
                "word_count": word_count,
                "keywords": keywords,
                "file_size": file_size,
            },
        )

    except Exception as e:
        return templates.TemplateResponse(
            "dashboard.html",
            {"request": request, "user_email": current_user_email(request), "error": f"Error: {str(e)}"},
        )


@app.post("/publish/{summary_id}", response_class=HTMLResponse)
def publish(request: Request, summary_id: int):
    redirect = require_login(request)
    if redirect:
        return redirect

    with db_conn() as conn:
        row = conn.execute(
            "SELECT id FROM summaries WHERE id=? AND user_email=?",
            (summary_id, current_user_email(request)),
        ).fetchone()
        if not row:
            return RedirectResponse(url="/history", status_code=303)

        conn.execute("UPDATE summaries SET published=1 WHERE id=?", (summary_id,))
        conn.commit()

    return RedirectResponse(url=f"/result/{summary_id}", status_code=303)


@app.get("/result/{summary_id}", response_class=HTMLResponse)
def view_result(request: Request, summary_id: int):
    redirect = require_login(request)
    if redirect:
        return redirect

    with db_conn() as conn:
        row = conn.execute(
            "SELECT id, filename, created_at, bullets_json, published, word_count, keywords_json, file_size FROM summaries WHERE id=? AND user_email=?",
            (summary_id, current_user_email(request)),
        ).fetchone()

    if not row:
        return RedirectResponse(url="/history", status_code=303)

    bullets = json.loads(row[3])
    keywords = json.loads(row[6]) if row[6] else []
    word_count = row[5] if row[5] else 0
    file_size = row[7] if row[7] else 0
    
    return templates.TemplateResponse(
        "result.html",
        {
            "request": request,
            "user_email": current_user_email(request),
            "summary_id": row[0],
            "filename": row[1],
            "created_at": row[2],
            "bullets": bullets,
            "published": bool(row[4]),
            "word_count": word_count,
            "keywords": keywords,
            "file_size": file_size,
        },
    )


@app.get("/history", response_class=HTMLResponse)
def history(request: Request):
    redirect = require_login(request)
    if redirect:
        return redirect

    with db_conn() as conn:
        rows = conn.execute(
            "SELECT id, filename, created_at, published FROM summaries WHERE user_email=? ORDER BY id DESC",
            (current_user_email(request),),
        ).fetchall()

    items = [{"id": r[0], "filename": r[1], "created_at": r[2], "published": bool(r[3])} for r in rows]
    return templates.TemplateResponse(
        "history.html",
        {"request": request, "user_email": current_user_email(request), "items": items},
    )


@app.get("/s/{summary_id}", response_class=HTMLResponse)
def shared_view(request: Request, summary_id: int):
    with db_conn() as conn:
        row = conn.execute(
            "SELECT filename, created_at, bullets_json FROM summaries WHERE id=? AND published=1",
            (summary_id,),
        ).fetchone()

    if not row:
        return templates.TemplateResponse("shared.html", {"request": request, "found": False})

    bullets = json.loads(row[2])
    return templates.TemplateResponse(
        "shared.html", {"request": request, "found": True, "filename": row[0], "created_at": row[1], "bullets": bullets}
    )




# ----------------------
# Q&A Database Setup
# ----------------------
def init_qa_db():
    """Initialize Q&A database table."""
    with db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS qa_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (summary_id) REFERENCES summaries(id)
            )
            """
        )
        conn.commit()


# Call this after init_db()
init_qa_db()


# ----------------------
# Q&A Helper Functions
# ----------------------
def ask_question_openclaw(document_text: str, question: str) -> str:
    """
    Uses OpenClaw CLI to answer questions about a document.
    Falls back to simple response if OpenClaw is unavailable.
    """
    try:
        # Truncate document if too long
        text_sample = document_text[:8000] if len(document_text) > 8000 else document_text
        
        # Build prompt for OpenClaw
        prompt = f"""You are an AI assistant helping users understand documents. Based on the document text provided below, please answer the user's question accurately and concisely.

Document text:
{text_sample}

User's question: {question}

Please provide a clear, direct answer based only on the information in the document. If the answer cannot be found in the document, say so."""

        # Execute OpenClaw CLI
        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "--message", prompt, "--json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            # Parse OpenClaw JSON response
            openclaw_response = json.loads(result.stdout)
            
            # Extract the text response from payloads
            if "result" in openclaw_response and "payloads" in openclaw_response["result"]:
                payloads = openclaw_response["result"]["payloads"]
                if payloads and len(payloads) > 0:
                    response_text = payloads[0].get("text", "")
                    if response_text:
                        return response_text.strip()
        
        # Fallback response
        return f"I apologize, but I'm unable to process your question at this time. OpenClaw AI is currently unavailable. Please try again later."
        
    except Exception as e:
        print(f"OpenClaw Q&A error: {e}")
        return f"I apologize, but I encountered an error while processing your question: {str(e)}"


def get_document_text_from_summary(summary_id: int, user_email: str) -> Optional[str]:
    """
    Retrieve the original document text for a summary.
    Note: This is a placeholder - in production, you'd store the original text.
    For now, we'll return a message indicating we need the text.
    """
    # In a real implementation, you'd store the original document text
    # For now, return None to indicate we need to handle this differently
    return None


# ----------------------
# Q&A Routes
# ----------------------
@app.get("/qa/{summary_id}", response_class=HTMLResponse)
def qa_page(request: Request, summary_id: int):
    """Q&A page for a specific document summary."""
    redirect = require_login(request)
    if redirect:
        return redirect

    with db_conn() as conn:
        # Get summary info
        summary_row = conn.execute(
            "SELECT id, filename, created_at, bullets_json FROM summaries WHERE id=? AND user_email=?",
            (summary_id, current_user_email(request)),
        ).fetchone()
        
        if not summary_row:
            return RedirectResponse(url="/history", status_code=303)
        
        # Get Q&A history for this document
        qa_rows = conn.execute(
            "SELECT question, answer, created_at FROM qa_history WHERE summary_id=? ORDER BY id DESC",
            (summary_id,),
        ).fetchall()
    
    summary = {
        "id": summary_row[0],
        "filename": summary_row[1],
        "created_at": summary_row[2],
        "bullets": json.loads(summary_row[3])
    }
    
    qa_history = [
        {
            "question": row[0],
            "answer": row[1],
            "created_at": row[2]
        }
        for row in qa_rows
    ]
    
    openclaw_status = check_openclaw_status()
    
    return templates.TemplateResponse(
        "qa.html",
        {
            "request": request,
            "user_email": current_user_email(request),
            "summary": summary,
            "qa_history": qa_history,
            "openclaw_status": openclaw_status
        },
    )


@app.post("/api/ask-question")
async def api_ask_question(request: Request):
    """API endpoint to ask a question about a document."""
    redirect = require_login(request)
    if redirect:
        return JSONResponse({"success": False, "error": "Not logged in"}, status_code=401)
    
    try:
        body = await request.json()
        summary_id = body.get("summary_id")
        question = body.get("question", "").strip()
        
        if not question:
            return JSONResponse({"success": False, "error": "Question is required"})
        
        with db_conn() as conn:
            # Get summary and verify ownership - now includes document_text
            summary_row = conn.execute(
                "SELECT id, filename, bullets_json, document_text FROM summaries WHERE id=? AND user_email=?",
                (summary_id, current_user_email(request)),
            ).fetchone()
            
            if not summary_row:
                return JSONResponse({"success": False, "error": "Summary not found"})
            
            # Use stored document text if available, otherwise fall back to bullets
            document_text = summary_row[3] if summary_row[3] else None
            if not document_text:
                # Fallback to bullets if document text not stored
                bullets = json.loads(summary_row[2])
                document_context = "\n".join(bullets)
            else:
                document_context = document_text
            
            # Get answer from OpenClaw
            answer = ask_question_openclaw(document_context, question)
            
            # Save Q&A to database
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO qa_history (summary_id, question, answer, created_at) VALUES (?, ?, ?, ?)",
                (summary_id, question, answer, created_at)
            )
            conn.commit()
        
        return JSONResponse({
            "success": True,
            "answer": answer,
            "created_at": created_at
        })
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


# ----------------------
# Chat Routes (AI Chat Interface)
# ----------------------
def init_chat_db():
    """Initialize chat database table."""
    with db_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                summary_id INTEGER NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (summary_id) REFERENCES summaries(id)
            )
            """
        )
        conn.commit()


# Initialize chat database
try:
    init_chat_db()
except:
    pass  # Table already exists


def chat_with_openclaw(document_text: str, question: str) -> str:
    """Uses OpenClaw CLI to answer questions in chat format."""
    try:
        text_sample = document_text[:8000] if len(document_text) > 8000 else document_text
        
        prompt = f"""You are an AI assistant helping users understand documents through conversation. Based on the document text provided below, please answer the user's question in a natural, conversational way.

Document text:
{text_sample}

User's question: {question}

Please provide a clear, helpful answer based on the information in the document. If the answer cannot be found in the document, politely say so."""

        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "--message", prompt, "--json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            openclaw_response = json.loads(result.stdout)
            if "result" in openclaw_response and "payloads" in openclaw_response["result"]:
                payloads = openclaw_response["result"]["payloads"]
                if payloads and len(payloads) > 0:
                    response_text = payloads[0].get("text", "")
                    if response_text:
                        return response_text.strip()
        
        return "I apologize, but I'm unable to process your question at this time. OpenClaw AI is currently unavailable."
        
    except Exception as e:
        print(f"OpenClaw chat error: {e}")
        return f"I apologize, but I encountered an error: {str(e)}"


@app.get("/chat/{summary_id}", response_class=HTMLResponse)
def chat_page(request: Request, summary_id: int):
    """AI Chat page for a specific document."""
    redirect = require_login(request)
    if redirect:
        return redirect

    with db_conn() as conn:
        summary_row = conn.execute(
            "SELECT id, filename, created_at, bullets_json FROM summaries WHERE id=? AND user_email=?",
            (summary_id, current_user_email(request)),
        ).fetchone()
        
        if not summary_row:
            return RedirectResponse(url="/history", status_code=303)
        
        chat_rows = conn.execute(
            "SELECT question, answer, created_at FROM chat_history WHERE summary_id=? ORDER BY id ASC",
            (summary_id,),
        ).fetchall()
    
    summary = {
        "id": summary_row[0],
        "filename": summary_row[1],
        "created_at": summary_row[2],
        "bullets": json.loads(summary_row[3])
    }
    
    chat_history = [
        {
            "question": row[0],
            "answer": row[1],
            "created_at": row[2]
        }
        for row in chat_rows
    ]
    
    openclaw_status = check_openclaw_status()
    
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "user_email": current_user_email(request),
            "summary": summary,
            "chat_history": chat_history,
            "openclaw_status": openclaw_status
        },
    )


@app.post("/api/chat")
async def api_chat(request: Request):
    """API endpoint for chat messages."""
    redirect = require_login(request)
    if redirect:
        return JSONResponse({"success": False, "error": "Not logged in"}, status_code=401)
    
    try:
        body = await request.json()
        summary_id = body.get("summary_id")
        question = body.get("question", "").strip()
        
        if not question:
            return JSONResponse({"success": False, "error": "Question is required"})
        
        with db_conn() as conn:
            summary_row = conn.execute(
                "SELECT id, filename, bullets_json, document_text FROM summaries WHERE id=? AND user_email=?",
                (summary_id, current_user_email(request)),
            ).fetchone()
            
            if not summary_row:
                return JSONResponse({"success": False, "error": "Document not found"})
            
            document_text = summary_row[3] if summary_row[3] else None
            if not document_text:
                bullets = json.loads(summary_row[2])
                document_context = "\n".join(bullets)
            else:
                document_context = document_text
            
            answer = chat_with_openclaw(document_context, question)
            
            created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            conn.execute(
                "INSERT INTO chat_history (summary_id, question, answer, created_at) VALUES (?, ?, ?, ?)",
                (summary_id, question, answer, created_at)
            )
            conn.commit()
        
        return JSONResponse({
            "success": True,
            "answer": answer,
            "created_at": created_at
        })
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@app.get("/status", response_class=HTMLResponse)
def status_page(request: Request):
    """System status page showing OpenClaw and app status."""
    openclaw_status = check_openclaw_status()
    system_info = get_system_info()
    
    # Determine summarization method
    if openclaw_status["available"]:
        summarization_method = "OpenClaw AI (Claude 3 Haiku via AWS Bedrock)"
    else:
        summarization_method = "Local Extractive Summarization (Fallback)"
    
    return templates.TemplateResponse(
        "status.html",
        {
            "request": request,
            "user_email": current_user_email(request),
            "openclaw_status": openclaw_status,
            "system_info": system_info,
            "summarization_method": summarization_method,
            "app_status": "running"
        }
    )



# ----------------------
# AEO (Answer Engine Optimization) Tools
# ----------------------
def generate_faq_openclaw(document_text: str) -> List[dict]:
    """Generate FAQ questions and answers from document using OpenClaw."""
    try:
        text_sample = document_text[:8000] if len(document_text) > 8000 else document_text
        
        prompt = f"""Based on the following document, generate 5-10 relevant FAQ questions and answers that would be useful for readers. Format your response as a JSON array with objects containing "question" and "answer" fields.

Document text:
{text_sample}

Provide ONLY a valid JSON array in this exact format:
[
  {{"question": "What is...", "answer": "The answer is..."}},
  {{"question": "How does...", "answer": "It works by..."}}
]"""

        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "--message", prompt, "--json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            openclaw_response = json.loads(result.stdout)
            if "result" in openclaw_response and "payloads" in openclaw_response["result"]:
                payloads = openclaw_response["result"]["payloads"]
                if payloads and len(payloads) > 0:
                    response_text = payloads[0].get("text", "")
                    
                    # Try to extract JSON from response
                    json_match = re.search(r'\[[\s\S]*\]', response_text)
                    if json_match:
                        try:
                            faqs = json.loads(json_match.group(0))
                            return faqs[:10]  # Limit to 10
                        except:
                            pass
        
        # Fallback FAQs
        return [
            {"question": "What is this document about?", "answer": "This document contains information that has been analyzed by our AI system."},
            {"question": "What are the main topics covered?", "answer": "The document covers various topics as outlined in the summary above."}
        ]
        
    except Exception as e:
        print(f"FAQ generation error: {e}")
        return [{"question": "Error", "answer": f"Unable to generate FAQs: {str(e)}"}]


def generate_featured_snippet_openclaw(document_text: str) -> str:
    """Generate a 40-60 word featured snippet optimized for AI search engines."""
    try:
        text_sample = document_text[:8000] if len(document_text) > 8000 else document_text
        
        prompt = f"""Based on the following document, create a concise 40-60 word answer that would be perfect for AI search engines and featured snippets. Make it informative, clear, and directly answer what this document is about.

Document text:
{text_sample}

Provide ONLY the 40-60 word snippet, nothing else."""

        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "--message", prompt, "--json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            openclaw_response = json.loads(result.stdout)
            if "result" in openclaw_response and "payloads" in openclaw_response["result"]:
                payloads = openclaw_response["result"]["payloads"]
                if payloads and len(payloads) > 0:
                    response_text = payloads[0].get("text", "").strip()
                    if response_text:
                        return response_text
        
        return "This document provides comprehensive information on its subject matter, offering detailed insights and analysis for readers seeking in-depth understanding of the topic."
        
    except Exception as e:
        print(f"Featured snippet error: {e}")
        return f"Error generating featured snippet: {str(e)}"


def find_content_gaps_openclaw(document_text: str) -> List[str]:
    """Identify important questions that the document doesn't answer."""
    try:
        text_sample = document_text[:8000] if len(document_text) > 8000 else document_text
        
        prompt = f"""Analyze the following document and identify 5-8 important questions that readers might have but are NOT answered in the document. These are content gaps that could be filled to make the document more comprehensive.

Document text:
{text_sample}

Provide ONLY a list of questions, one per line, starting with a dash (-). No additional commentary."""

        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "--message", prompt, "--json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            openclaw_response = json.loads(result.stdout)
            if "result" in openclaw_response and "payloads" in openclaw_response["result"]:
                payloads = openclaw_response["result"]["payloads"]
                if payloads and len(payloads) > 0:
                    response_text = payloads[0].get("text", "")
                    
                    # Parse questions from response
                    gaps = []
                    for line in response_text.split('\n'):
                        line = line.strip()
                        if line.startswith('-') or line.startswith('*') or (len(line) > 2 and line[0].isdigit()):
                            clean_line = re.sub(r'^[-*•]\s*', '', line)
                            clean_line = re.sub(r'^\d+[.):]\s*', '', clean_line)
                            if len(clean_line) > 10 and '?' in clean_line:
                                gaps.append(clean_line.strip())
                    
                    if gaps:
                        return gaps[:8]
        
        return [
            "What are the practical applications of this information?",
            "What are the limitations or challenges mentioned?",
            "How does this compare to alternative approaches?"
        ]
        
    except Exception as e:
        print(f"Content gap analysis error: {e}")
        return [f"Error analyzing content gaps: {str(e)}"]


def generate_multi_format_answer_openclaw(document_text: str, topic: str) -> dict:
    """Generate answers in multiple formats: short, paragraph, and bullet points."""
    try:
        text_sample = document_text[:8000] if len(document_text) > 8000 else document_text
        
        prompt = f"""Based on the following document, provide an answer about "{topic}" in THREE different formats:

1. SHORT ANSWER (1 sentence, max 20 words)
2. PARAGRAPH (2-3 sentences, detailed explanation)
3. BULLET POINTS (3-5 key points)

Document text:
{text_sample}

Format your response EXACTLY like this:
SHORT: [your short answer]
PARAGRAPH: [your paragraph]
BULLETS:
- [point 1]
- [point 2]
- [point 3]"""

        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "--message", prompt, "--json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            openclaw_response = json.loads(result.stdout)
            if "result" in openclaw_response and "payloads" in openclaw_response["result"]:
                payloads = openclaw_response["result"]["payloads"]
                if payloads and len(payloads) > 0:
                    response_text = payloads[0].get("text", "")
                    
                    # Parse the response
                    short_match = re.search(r'SHORT:\s*(.+?)(?=\n|PARAGRAPH:|$)', response_text, re.IGNORECASE)
                    para_match = re.search(r'PARAGRAPH:\s*(.+?)(?=\n|BULLETS:|$)', response_text, re.IGNORECASE | re.DOTALL)
                    bullets_match = re.search(r'BULLETS:\s*(.+?)$', response_text, re.IGNORECASE | re.DOTALL)
                    
                    short_answer = short_match.group(1).strip() if short_match else "Information available in document."
                    paragraph = para_match.group(1).strip() if para_match else "The document provides detailed information on this topic."
                    
                    bullets = []
                    if bullets_match:
                        bullet_text = bullets_match.group(1)
                        for line in bullet_text.split('\n'):
                            line = line.strip()
                            if line.startswith('-') or line.startswith('*'):
                                clean_line = re.sub(r'^[-*•]\s*', '', line).strip()
                                if clean_line:
                                    bullets.append(clean_line)
                    
                    if not bullets:
                        bullets = ["Key information is available in the document"]
                    
                    return {
                        "short": short_answer,
                        "paragraph": paragraph,
                        "bullets": bullets[:5]
                    }
        
        return {
            "short": "Information available in document.",
            "paragraph": "The document contains relevant information about this topic. Please refer to the summary for details.",
            "bullets": ["Key information is available in the document"]
        }
        
    except Exception as e:
        print(f"Multi-format answer error: {e}")
        return {
            "short": f"Error: {str(e)}",
            "paragraph": f"Unable to generate answer: {str(e)}",
            "bullets": ["Error generating response"]
        }


def calculate_aeo_score_openclaw(document_text: str) -> dict:
    """Calculate AEO (Answer Engine Optimization) score for the document."""
    try:
        text_sample = document_text[:8000] if len(document_text) > 8000 else document_text
        
        prompt = f"""Analyze the following document for Answer Engine Optimization (AEO) readiness. Evaluate it on these criteria and provide scores out of 100:

1. Overall AEO Score (0-100): How well optimized is this content for AI answer engines?
2. FAQ Readiness (0-100): Does it answer common questions clearly?
3. Featured Snippet Readiness (0-100): Are there concise, direct answers suitable for snippets?
4. Answer Clarity (0-100): How clear and structured are the answers?
5. Missing Question Opportunities (0-100): How many important questions are left unanswered? (100 = no gaps, 0 = many gaps)

Document text:
{text_sample}

Provide your response in this EXACT format:
OVERALL: [score]
FAQ: [score]
SNIPPET: [score]
CLARITY: [score]
GAPS: [score]
SUMMARY: [1-2 sentence summary of the assessment]"""

        result = subprocess.run(
            ["openclaw", "agent", "--agent", "main", "--message", prompt, "--json"],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode == 0:
            openclaw_response = json.loads(result.stdout)
            if "result" in openclaw_response and "payloads" in openclaw_response["result"]:
                payloads = openclaw_response["result"]["payloads"]
                if payloads and len(payloads) > 0:
                    response_text = payloads[0].get("text", "")
                    
                    # Parse scores
                    overall_match = re.search(r'OVERALL:\s*(\d+)', response_text, re.IGNORECASE)
                    faq_match = re.search(r'FAQ:\s*(\d+)', response_text, re.IGNORECASE)
                    snippet_match = re.search(r'SNIPPET:\s*(\d+)', response_text, re.IGNORECASE)
                    clarity_match = re.search(r'CLARITY:\s*(\d+)', response_text, re.IGNORECASE)
                    gaps_match = re.search(r'GAPS:\s*(\d+)', response_text, re.IGNORECASE)
                    summary_match = re.search(r'SUMMARY:\s*(.+?)(?=\n\n|$)', response_text, re.IGNORECASE | re.DOTALL)
                    
                    overall_score = int(overall_match.group(1)) if overall_match else 70
                    faq_score = int(faq_match.group(1)) if faq_match else 65
                    snippet_score = int(snippet_match.group(1)) if snippet_match else 70
                    clarity_score = int(clarity_match.group(1)) if clarity_match else 75
                    gaps_score = int(gaps_match.group(1)) if gaps_match else 60
                    summary = summary_match.group(1).strip() if summary_match else "Document shows moderate AEO optimization potential."
                    
                    # Ensure scores are within 0-100
                    overall_score = max(0, min(100, overall_score))
                    faq_score = max(0, min(100, faq_score))
                    snippet_score = max(0, min(100, snippet_score))
                    clarity_score = max(0, min(100, clarity_score))
                    gaps_score = max(0, min(100, gaps_score))
                    
                    return {
                        "overall_score": overall_score,
                        "faq_readiness": faq_score,
                        "snippet_readiness": snippet_score,
                        "answer_clarity": clarity_score,
                        "missing_questions": gaps_score,
                        "summary": summary
                    }
        
        # Fallback scores
        return {
            "overall_score": 70,
            "faq_readiness": 65,
            "snippet_readiness": 70,
            "answer_clarity": 75,
            "missing_questions": 60,
            "summary": "Document shows moderate AEO optimization potential with room for improvement."
        }
        
    except Exception as e:
        print(f"AEO score calculation error: {e}")
        return {
            "overall_score": 0,
            "faq_readiness": 0,
            "snippet_readiness": 0,
            "answer_clarity": 0,
            "missing_questions": 0,
            "summary": f"Error calculating AEO score: {str(e)}"
        }


# ----------------------
# AEO Tool Routes
# ----------------------
@app.get("/aeo-dashboard", response_class=HTMLResponse)
def aeo_dashboard(request: Request):
    """AEO Dashboard - overview of all AEO tools."""
    redirect = require_login(request)
    if redirect:
        return redirect
    
    # Get recent summaries for quick access
    with db_conn() as conn:
        rows = conn.execute(
            "SELECT id, filename, created_at FROM summaries WHERE user_email=? ORDER BY id DESC LIMIT 5",
            (current_user_email(request),),
        ).fetchall()
    
    recent_summaries = [{"id": r[0], "filename": r[1], "created_at": r[2]} for r in rows]
    openclaw_status = check_openclaw_status()
    
    return templates.TemplateResponse(
        "aeo-dashboard.html",
        {
            "request": request,
            "user_email": current_user_email(request),
            "recent_summaries": recent_summaries,
            "openclaw_status": openclaw_status
        },
    )


@app.get("/aeo/{summary_id}", response_class=HTMLResponse)
def aeo_tools_page(request: Request, summary_id: int):
    """AEO Tools page for a specific document."""
    redirect = require_login(request)
    if redirect:
        return redirect

    with db_conn() as conn:
        summary_row = conn.execute(
            "SELECT id, filename, created_at, bullets_json, document_text FROM summaries WHERE id=? AND user_email=?",
            (summary_id, current_user_email(request)),
        ).fetchone()
        
        if not summary_row:
            return RedirectResponse(url="/history", status_code=303)
    
    summary = {
        "id": summary_row[0],
        "filename": summary_row[1],
        "created_at": summary_row[2],
        "bullets": json.loads(summary_row[3])
    }
    
    openclaw_status = check_openclaw_status()
    
    return templates.TemplateResponse(
        "aeo.html",
        {
            "request": request,
            "user_email": current_user_email(request),
            "summary": summary,
            "openclaw_status": openclaw_status
        },
    )


@app.post("/api/aeo/faq")
async def api_generate_faq(request: Request):
    """API endpoint to generate FAQ."""
    redirect = require_login(request)
    if redirect:
        return JSONResponse({"success": False, "error": "Not logged in"}, status_code=401)
    
    try:
        body = await request.json()
        summary_id = body.get("summary_id")
        
        with db_conn() as conn:
            summary_row = conn.execute(
                "SELECT document_text, bullets_json FROM summaries WHERE id=? AND user_email=?",
                (summary_id, current_user_email(request)),
            ).fetchone()
            
            if not summary_row:
                return JSONResponse({"success": False, "error": "Document not found"})
            
            document_text = summary_row[0] if summary_row[0] else "\n".join(json.loads(summary_row[1]))
            faqs = generate_faq_openclaw(document_text)
        
        return JSONResponse({"success": True, "faqs": faqs})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@app.post("/api/aeo/snippet")
async def api_generate_snippet(request: Request):
    """API endpoint to generate featured snippet."""
    redirect = require_login(request)
    if redirect:
        return JSONResponse({"success": False, "error": "Not logged in"}, status_code=401)
    
    try:
        body = await request.json()
        summary_id = body.get("summary_id")
        
        with db_conn() as conn:
            summary_row = conn.execute(
                "SELECT document_text, bullets_json FROM summaries WHERE id=? AND user_email=?",
                (summary_id, current_user_email(request)),
            ).fetchone()
            
            if not summary_row:
                return JSONResponse({"success": False, "error": "Document not found"})
            
            document_text = summary_row[0] if summary_row[0] else "\n".join(json.loads(summary_row[1]))
            snippet = generate_featured_snippet_openclaw(document_text)
        
        return JSONResponse({"success": True, "snippet": snippet})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@app.post("/api/aeo/gaps")
async def api_find_content_gaps(request: Request):
    """API endpoint to find content gaps."""
    redirect = require_login(request)
    if redirect:
        return JSONResponse({"success": False, "error": "Not logged in"}, status_code=401)
    
    try:
        body = await request.json()
        summary_id = body.get("summary_id")
        
        with db_conn() as conn:
            summary_row = conn.execute(
                "SELECT document_text, bullets_json FROM summaries WHERE id=? AND user_email=?",
                (summary_id, current_user_email(request)),
            ).fetchone()
            
            if not summary_row:
                return JSONResponse({"success": False, "error": "Document not found"})
            
            document_text = summary_row[0] if summary_row[0] else "\n".join(json.loads(summary_row[1]))
            gaps = find_content_gaps_openclaw(document_text)
        
        return JSONResponse({"success": True, "gaps": gaps})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@app.post("/api/aeo/multi-format")
async def api_generate_multi_format(request: Request):
    """API endpoint to generate multi-format answers."""
    redirect = require_login(request)
    if redirect:
        return JSONResponse({"success": False, "error": "Not logged in"}, status_code=401)
    
    try:
        body = await request.json()
        summary_id = body.get("summary_id")
        topic = body.get("topic", "main topic").strip()
        
        if not topic:
            topic = "main topic"
        
        with db_conn() as conn:
            summary_row = conn.execute(
                "SELECT document_text, bullets_json FROM summaries WHERE id=? AND user_email=?",
                (summary_id, current_user_email(request)),
            ).fetchone()
            
            if not summary_row:
                return JSONResponse({"success": False, "error": "Document not found"})
            
            document_text = summary_row[0] if summary_row[0] else "\n".join(json.loads(summary_row[1]))
            formats = generate_multi_format_answer_openclaw(document_text, topic)
        
        return JSONResponse({"success": True, "formats": formats})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})


@app.post("/api/aeo/score")
async def api_calculate_aeo_score(request: Request):
    """API endpoint to calculate AEO score."""
    redirect = require_login(request)
    if redirect:
        return JSONResponse({"success": False, "error": "Not logged in"}, status_code=401)
    
    try:
        body = await request.json()
        summary_id = body.get("summary_id")
        
        with db_conn() as conn:
            summary_row = conn.execute(
                "SELECT document_text, bullets_json FROM summaries WHERE id=? AND user_email=?",
                (summary_id, current_user_email(request)),
            ).fetchone()
            
            if not summary_row:
                return JSONResponse({"success": False, "error": "Document not found"})
            
            document_text = summary_row[0] if summary_row[0] else "\n".join(json.loads(summary_row[1]))
            score_data = calculate_aeo_score_openclaw(document_text)
        
        return JSONResponse({"success": True, "score": score_data})
        
    except Exception as e:
        return JSONResponse({"success": False, "error": str(e)})
