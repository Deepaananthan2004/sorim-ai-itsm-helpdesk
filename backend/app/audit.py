from uuid import uuid4
from .storage import get_store, now_iso

def record_event(actor, action, status, request_id=None, ticket_id=None, target="application", details=None, validation=None):
    event = {"id":f"AUD-{uuid4().hex[:10].upper()}","timestamp":now_iso(),"actor":actor,
             "action":action,"status":status,"request_id":request_id,"ticket_id":ticket_id,
             "target":target,"details":details or {},"validation_outcome":validation}
    return get_store().insert("audit",event)
