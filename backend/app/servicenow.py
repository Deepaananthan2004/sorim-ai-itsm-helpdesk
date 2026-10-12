from uuid import uuid4
import httpx
from .core.config import get_settings
from .storage import get_store

class ServiceNowAdapter:
    def __init__(self): self.settings = get_settings()
    @property
    def mode(self): return self.settings.servicenow_mode.lower()
    def _real(self, method, table, payload=None, sys_id=None):
        s=self.settings
        if not (s.servicenow_instance_url and s.servicenow_username and s.servicenow_password):
            raise RuntimeError("Real ServiceNow mode requires URL, username, and password")
        url=f"{s.servicenow_instance_url.rstrip('/')}/api/now/table/{table}"
        if sys_id: url += f"/{sys_id}"
        r=httpx.request(method,url,auth=(s.servicenow_username,s.servicenow_password),json=payload,timeout=12,
                        headers={"Accept":"application/json"})
        r.raise_for_status(); data=r.json(); return data.get("result",data)
    def create_incident(self,ticket):
        payload={"short_description":ticket["summary"],"description":ticket["description"],
                 "category":ticket.get("servicenow_category","network"),"subcategory":ticket.get("subcategory",""),
                 "priority":{"P1":"1","P2":"2","P3":"3","P4":"4"}.get(ticket.get("priority"),"3"),
                 "impact":"3" if ticket.get("impact")=="Individual" else "2",
                 "urgency":"1" if ticket.get("urgency")=="High" else "2",
                 "assignment_group":ticket.get("assigned_group","")}
        if self.mode=="real":
            x=self._real("POST","incident",payload); return {"mode":"real","sys_id":x.get("sys_id"),"number":x.get("number"),"result":x}
        ref=f"MOCK-INC{uuid4().hex[:6].upper()}"
        row={"id":ref,"number":ref,"table":"incident","mode":"mock","payload":payload,"state":"New"}
        get_store().insert("servicenow",row)
        return {"mode":"mock","sys_id":ref,"number":ref,"result":row}
    def get_incident(self,sys_id):
        return self._real("GET","incident",sys_id=sys_id) if self.mode=="real" else get_store().get("servicenow",sys_id)
    def update_incident(self,sys_id,payload):
        if self.mode=="real": return self._real("PATCH","incident",payload,sys_id)
        return get_store().update("servicenow",sys_id,{"payload_update":payload,**payload})
    def create_service_request(self,request):
        payload={"short_description":f"Software request: {request['software_name']}","description":request.get("business_justification","Required for work")}
        if self.mode=="real":
            x=self._real("POST","sc_request",payload); return {"mode":"real","sys_id":x.get("sys_id"),"number":x.get("number"),"result":x}
        ref=f"MOCK-REQ{uuid4().hex[:6].upper()}"
        row={"id":ref,"number":ref,"table":"sc_request","mode":"mock","payload":payload,"state":"Requested"}
        get_store().insert("servicenow",row)
        return {"mode":"mock","sys_id":ref,"number":ref,"result":row}
