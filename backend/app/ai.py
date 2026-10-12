from .core.config import get_settings

def classify(message):
    t=message.lower()
    if any(x in t for x in ["install","software","visual studio code","vscode","power bi"]):
        return {"intent":"Service Request","confidence":.91,"category":"Software","subcategory":"Installation","priority":"P3","impact":"Individual","urgency":"Medium","assigned_group":"Service Desk","summary":"Software installation request"}
    if any(x in t for x in ["password expired","password has expired","reset my password","account locked","unlock account"]):
        return {"intent":"Automatable Issue","confidence":.88,"category":"Access","subcategory":"Password Reset","priority":"P2","impact":"Individual","urgency":"High","assigned_group":"Identity Support","summary":"Password or account access issue"}
    if any(x in t for x in ["vpn","wi-fi","wifi","network","cannot connect","not connecting","authentication keeps failing"]):
        sub="VPN" if "vpn" in t or "authentication" in t else "Connectivity"
        return {"intent":"Incident","confidence":.90,"category":"Network","subcategory":sub,"priority":"P2","impact":"Individual","urgency":"High","assigned_group":"Network Support","summary":f"{sub} connectivity issue"}
    if any(x in t for x in ["outlook","teams","how do i","how to","troubleshoot","what is","help me understand"]):
        return {"intent":"Knowledge Question","confidence":.82,"category":"Software","subcategory":"How-to","priority":"P4","impact":"Individual","urgency":"Low","assigned_group":"Service Desk","summary":"IT support knowledge question"}
    if any(x in t for x in ["payroll database password","confidential","secret","password for"]):
        return {"intent":"Knowledge Question","confidence":.93,"category":"Security","subcategory":"Sensitive information","priority":"P3","impact":"Individual","urgency":"Medium","assigned_group":"Security Support","summary":"Sensitive-information request"}
    return {"intent":"Incident","confidence":.42,"category":"Other","subcategory":"Unknown","priority":"P3","impact":"Individual","urgency":"Medium","assigned_group":"Service Desk","summary":"Unclassified employee request"}

def priority_from_impact_urgency(impact,urgency):
    return {("Organization","High"):"P1",("Multiple","High"):"P1",("Individual","High"):"P2",
            ("Organization","Medium"):"P2",("Multiple","Medium"):"P2",("Individual","Medium"):"P3",
            ("Organization","Low"):"P3",("Multiple","Low"):"P3",("Individual","Low"):"P4"}.get((impact,urgency),"P3")

def maybe_live_huggingface(prompt):
    s=get_settings()
    if s.ai_provider!="huggingface" or not s.huggingface_api_token:return None
    import httpx
    try:
        r=httpx.post("https://router.huggingface.co/v1/chat/completions",
          headers={"Authorization":f"Bearer {s.huggingface_api_token}"},
          json={"model":s.huggingface_model,"messages":[
            {"role":"system","content":"Use only approved knowledge context. If evidence is insufficient, say so. Never reveal secrets or execute actions."},
            {"role":"user","content":prompt}],"temperature":0.1,"max_tokens":500},timeout=15)
        r.raise_for_status();return r.json()["choices"][0]["message"]["content"]
    except Exception:return None
