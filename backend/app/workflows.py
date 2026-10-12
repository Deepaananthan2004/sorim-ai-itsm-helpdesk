from uuid import uuid4
from .ai import classify,priority_from_impact_urgency,maybe_live_huggingface
from .knowledge import KnowledgeService
from .storage import get_store,now_iso
from .servicenow import ServiceNowAdapter
from .audit import record_event
from .core.config import get_settings

SOFTWARE_CATALOG=[
 {"id":"vscode","name":"Visual Studio Code","description":"Lightweight code editor","platform":"Windows/macOS/Linux","approval_required":False},
 {"id":"python","name":"Python","description":"Python runtime for development","platform":"Windows/macOS/Linux","approval_required":True},
 {"id":"git","name":"Git","description":"Version control client","platform":"Windows/macOS/Linux","approval_required":False},
 {"id":"teams","name":"Microsoft Teams","description":"Enterprise collaboration","platform":"Windows/macOS","approval_required":False},
 {"id":"powerbi","name":"Power BI Desktop","description":"Business intelligence desktop application","platform":"Windows","approval_required":True}]
def new_id(prefix):return f"{prefix}-{uuid4().hex[:10].upper()}"

class WorkflowService:
    def __init__(self):self.knowledge=KnowledgeService();self.sn=ServiceNowAdapter();self.settings=get_settings()
    def create_ticket(self,description,user_id="demo.employee",idempotency_key=None):
        store=get_store()
        if idempotency_key:
            old=next((t for t in store.all("tickets") if t.get("idempotency_key")==idempotency_key),None)
            if old:return old
        ai=classify(description);ai["priority"]=priority_from_impact_urgency(ai["impact"],ai["urgency"])
        rag=self.knowledge.answer(description)
        ticket={"id":new_id("INC"),"user_id":user_id,"description":description,"intent":ai["intent"],
          "category":ai["category"],"subcategory":ai["subcategory"],"priority":ai["priority"],"impact":ai["impact"],
          "urgency":ai["urgency"],"assigned_group":ai["assigned_group"],"summary":ai["summary"],
          "suggested_resolution":rag["answer"] if rag["grounded"] else None,"sources":rag["sources"],
          "confidence":ai["confidence"],"state":"Open","ai_resolved":False,"servicenow_mode":self.sn.mode,
          "idempotency_key":idempotency_key,"created_at":now_iso()}
        try:
            sn=self.sn.create_incident(ticket);ticket.update({"servicenow_reference":sn.get("number"),"servicenow_sys_id":sn.get("sys_id"),"servicenow_mode":sn.get("mode"),"servicenow_status":"created"})
        except Exception as exc:ticket.update({"servicenow_status":"failed","servicenow_error":str(exc)[:250]})
        store.insert("tickets",ticket)
        record_event("employee","incident_created","success",request_id=ticket["id"],ticket_id=ticket["id"],target=f"servicenow:{ticket['servicenow_mode']}",details={"reference":ticket.get("servicenow_reference"),"intent":ticket["intent"]})
        return ticket
    def chat(self,message,user_id="demo.employee",conversation_id=None,create_ticket=False):
        rid=new_id("CHAT");ai=classify(message);rag=self.knowledge.answer(message);confidence=ai["confidence"]
        escalation=confidence<self.settings.ai_confidence_threshold or not rag["grounded"]
        answer=rag["answer"] if rag["grounded"] else "I don't have enough approved knowledge to answer reliably. I can help escalate this to the IT helpdesk."
        sensitive=any(x in message.lower() for x in ["payroll database password","confidential internal","secret"])
        if sensitive:
            answer="I can't provide confidential credentials or secrets. Please use the approved access-management process or contact IT/security."
            escalation=True;rag={"sources":[],"grounded":False}
        provider="offline_rules"
        if self.settings.ai_provider=="huggingface" and self.settings.huggingface_api_token and rag["grounded"]:
            generated=maybe_live_huggingface("Question: "+message+"\nApproved excerpts:\n"+"\n".join(s["excerpt"] for s in rag["sources"]))
            if generated:answer=generated;provider="huggingface"
            else:provider="offline_fallback"
        ticket=None;request_id=None
        if ai["intent"]=="Incident" and create_ticket:ticket=self.create_ticket(message,user_id)
        if ai["intent"]=="Service Request":
            match=self.find_software(message)
            if match:request_id=self.create_software_request(match["id"],user_id,"Requested through employee chatbot")["id"]
        get_store().insert("chats",{"id":rid,"user_id":user_id,"conversation_id":conversation_id,"message":message,"response":answer,"intent":ai["intent"],"confidence":confidence,"created_at":now_iso()})
        record_event("system","chat_routed","escalated" if escalation else "success",request_id=rid,details={"intent":ai["intent"],"grounded":rag["grounded"],"provider":provider})
        return {"request_id":rid,"intent":ai["intent"],"message":answer,"suggested_resolution":rag["answer"] if rag["grounded"] else None,
          "sources":rag["sources"],"confidence":confidence,"escalation_recommended":escalation,
          "automation_eligible":ai["intent"]=="Automatable Issue","ticket_id":ticket["id"] if ticket else None,
          "service_request_id":request_id,"workflow_status":"escalated" if escalation else "answered","provider":provider}
    def find_software(self,text):
        q=text.lower()
        return next((x for x in SOFTWARE_CATALOG if x["id"]==q or x["name"].lower() in q or q in x["name"].lower()),None)
    def create_software_request(self,software_id,user_id,justification):
        item=self.find_software(software_id)
        if not item:raise ValueError("Unknown software catalog item")
        status="Pending Approval" if item["approval_required"] else "Submitted"
        req={"id":new_id("SWR"),"software_id":item["id"],"software_name":item["name"],"user_id":user_id,
          "business_justification":justification,"status":status,"approval_required":item["approval_required"],
          "provisioning_result":None,"servicenow_mode":self.sn.mode,"created_at":now_iso()}
        try:
            sn=self.sn.create_service_request(req);req.update({"servicenow_reference":sn.get("number"),"servicenow_sys_id":sn.get("sys_id")})
        except Exception as exc:req["servicenow_error"]=str(exc)[:250]
        if status=="Submitted":
            req["status"]="Provisioning";req["provisioning_result"]={"success":True,"mode":"mock_simulation","message":f"Simulated provisioning completed for {item['name']}. No device was modified."}
            req["status"]="Completed"
        get_store().insert("software_requests",req)
        record_event("employee","software_request_created","success",request_id=req["id"],target=f"servicenow:{req['servicenow_mode']}",details={"software":item["name"],"status":req["status"],"reference":req.get("servicenow_reference")})
        return req
    def execute_automation(self,issue,ticket_id=None,action=None,authorized=False,approval_granted=False):
        rid=new_id("AUTO");ai=classify(issue)
        if not authorized:
            out={"id":rid,"status":"blocked","action":action or "password_reset_simulation","message":"Automation blocked: caller authorization is required.","validated":False}
            get_store().insert("automation_actions",out);record_event("system","automation_blocked","blocked",request_id=rid,ticket_id=ticket_id,details={"reason":"authorization_required"});return out
        chosen=action or ("password_reset_simulation" if ai["intent"]=="Automatable Issue" else "vpn_status_check")
        allowed={"password_reset_simulation","account_unlock_simulation","vpn_status_check","service_status_check","cache_clear_simulation","application_restart_simulation"}
        if chosen not in allowed:raise ValueError("Action is not in the automation allowlist")
        if chosen in {"password_reset_simulation","account_unlock_simulation","application_restart_simulation","cache_clear_simulation"} and not approval_granted:
            out={"id":rid,"status":"pending_approval","action":chosen,"message":"This action requires explicit approval before execution.","validated":False}
            get_store().insert("automation_actions",out);record_event("system","automation_pending_approval","pending",request_id=rid,ticket_id=ticket_id,details={"action":chosen});return out
        out={"id":rid,"ticket_id":ticket_id,"action":chosen,"status":"completed","message":f"Mock simulation for {chosen} completed. No real account or device was changed.","validated":True,"validation_outcome":"mock_postcondition_passed","mode":"mock_simulation","created_at":now_iso()}
        get_store().insert("automation_actions",out)
        if ticket_id:
            get_store().update("tickets",ticket_id,{"state":"Resolved","ai_resolved":True,"resolution_note":out["message"]})
            t=get_store().get("tickets",ticket_id)
            if t and t.get("servicenow_sys_id"):
                try:self.sn.update_incident(t["servicenow_sys_id"],{"state":"6","close_notes":out["message"]})
                except Exception as exc:record_event("system","servicenow_update","failed",request_id=rid,ticket_id=ticket_id,details={"error":str(exc)[:200]})
        record_event("system","automation_executed","success",request_id=rid,ticket_id=ticket_id,target="mock_simulation",details={"action":chosen},validation="mock_postcondition_passed")
        return out
