from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .core.config import get_settings
from .schemas import ChatRequest,TicketCreate,TicketUpdate,AutomationRequest,KnowledgeSearchRequest,SoftwareRequestCreate,ResolveRequest
from .storage import get_store
from .knowledge import KnowledgeService
from .workflows import WorkflowService,SOFTWARE_CATALOG
from .audit import record_event

settings=get_settings()
@asynccontextmanager
async def lifespan(app):
    get_store()
    yield
app=FastAPI(title=settings.app_name,version="1.0.0",description="Hackathon ITSM automation prototype",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=settings.origins,allow_credentials=False,allow_methods=["GET","POST","PATCH","OPTIONS"],allow_headers=["Content-Type","Authorization","Idempotency-Key"])
def workflow():return WorkflowService()

@app.get("/")
def root():return {"name":settings.app_name,"docs":"/docs","mode":{"storage":settings.storage_mode,"servicenow":settings.servicenow_mode,"ai":settings.ai_provider,"embeddings":settings.embedding_mode}}
@app.get("/api/health")
def health():return {"status":"ok","app":settings.app_name}
@app.get("/api/health/ready")
def ready():
    try:
        store=get_store()
        return {"status":"ready","storage":settings.storage_mode,"servicenow_mode":settings.servicenow_mode,"ai_provider":settings.ai_provider,"embedding_mode":settings.embedding_mode,"collections":store.names}
    except Exception as exc:raise HTTPException(503,detail=f"Readiness check failed: {str(exc)[:200]}")
@app.post("/api/chat")
def chat(body:ChatRequest):
    try:return workflow().chat(body.message,body.user_id,body.conversation_id,body.create_ticket)
    except Exception as exc:
        record_event("system","chat_failed","failed",details={"error":str(exc)[:200]})
        raise HTTPException(500,detail="Chat workflow failed. Check backend configuration and logs.")
@app.post("/api/tickets",status_code=201)
def create_ticket(body:TicketCreate):
    try:return workflow().create_ticket(body.description,body.user_id,body.idempotency_key)
    except Exception as exc:
        record_event("system","ticket_creation_failed","failed",details={"error":str(exc)[:200]})
        raise HTTPException(500,detail="Ticket creation failed. Check configured storage and ServiceNow mode.")
@app.get("/api/tickets")
def list_tickets(limit:int=Query(100,ge=1,le=500),offset:int=Query(0,ge=0)):
    rows=sorted(get_store().all("tickets"),key=lambda x:x.get("created_at",""),reverse=True)
    return {"items":rows[offset:offset+limit],"total":len(rows),"limit":limit,"offset":offset}
@app.get("/api/tickets/{ticket_id}")
def get_ticket(ticket_id:str):
    x=get_store().get("tickets",ticket_id)
    if not x:raise HTTPException(404,"Ticket not found")
    return x
@app.patch("/api/tickets/{ticket_id}")
def update_ticket(ticket_id:str,body:TicketUpdate):
    x=get_store().update("tickets",ticket_id,body.model_dump(exclude_none=True))
    if not x:raise HTTPException(404,"Ticket not found")
    record_event("helpdesk","ticket_updated","success",request_id=ticket_id,ticket_id=ticket_id)
    return x
@app.post("/api/tickets/{ticket_id}/resolve")
def resolve_ticket(ticket_id:str,body:ResolveRequest):
    if not get_store().get("tickets",ticket_id):raise HTTPException(404,"Ticket not found")
    x=get_store().update("tickets",ticket_id,{"state":"Resolved","resolution_note":body.resolution_notes,"ai_resolved":False})
    record_event("helpdesk","ticket_resolved","success",request_id=ticket_id,ticket_id=ticket_id)
    return x
@app.post("/api/automation/execute")
def execute_automation(body:AutomationRequest):
    try:return workflow().execute_automation(body.issue,body.ticket_id,body.action,body.authorized,body.approval_granted)
    except ValueError as exc:raise HTTPException(400,str(exc))
    except Exception:raise HTTPException(500,"Automation failed; inspect server logs and audit trail.")
@app.get("/api/automation/actions")
def automation_actions(limit:int=Query(100,ge=1,le=500)):
    rows=get_store().all("automation_actions");return {"items":rows[-limit:][::-1],"total":len(rows)}
@app.get("/api/knowledge")
def list_knowledge():
    seen={}
    for x in get_store().all("knowledge"):seen[x["article_id"]]={k:v for k,v in x.items() if k!="chunk_id"}
    return {"items":list(seen.values()),"total":len(seen)}
@app.post("/api/knowledge/search")
def search_knowledge(body:KnowledgeSearchRequest):
    svc=workflow().knowledge
    if not svc.chunks:svc.ingest_directory()
    return {"query":body.query,"results":svc.search(body.query,body.top_k)}
@app.post("/api/knowledge/ingest")
def ingest_knowledge():
    try:return KnowledgeService().ingest_directory()
    except Exception as exc:raise HTTPException(500,detail=f"Knowledge ingestion failed: {str(exc)[:200]}")
@app.get("/api/software/catalog")
def software_catalog():return {"items":SOFTWARE_CATALOG}
@app.post("/api/software/requests",status_code=201)
def create_software_request(body:SoftwareRequestCreate):
    try:return workflow().create_software_request(body.software_id,body.user_id,body.business_justification)
    except ValueError as exc:raise HTTPException(404,str(exc))
@app.get("/api/software/requests")
def list_software_requests(limit:int=Query(100,ge=1,le=500)):
    rows=get_store().all("software_requests");return {"items":rows[-limit:][::-1],"total":len(rows)}
@app.get("/api/audit")
def audit(limit:int=Query(100,ge=1,le=500)):
    rows=get_store().all("audit");return {"items":rows[-limit:][::-1],"total":len(rows)}
@app.get("/api/dashboard/stats")
def dashboard_stats():
    store=get_store();t=store.all("tickets");s=store.all("software_requests");a=store.all("automation_actions")
    return {"total_tickets":len(t),"open_tickets":sum(x.get("state") not in ("Resolved","Closed") for x in t),
      "resolved_tickets":sum(x.get("state") in ("Resolved","Closed") for x in t),"ai_resolved_tickets":sum(bool(x.get("ai_resolved")) for x in t),
      "escalated_tickets":sum(x.get("confidence",1)<settings.ai_confidence_threshold for x in t),"software_requests":len(s),
      "pending_software_requests":sum(x.get("status") in ("Submitted","Pending Approval","Provisioning") for x in s),
      "automation_success":sum(x.get("status")=="completed" for x in a),"automation_failed":sum(x.get("status") in ("failed","blocked") for x in a),
      "recent_tickets":sorted(t,key=lambda x:x.get("created_at",""),reverse=True)[:5]}
