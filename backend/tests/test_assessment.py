def test_health(client):
    assert client.get("/api/health").status_code==200
    assert client.get("/api/health/ready").json()["status"]=="ready"

def test_vpn_incident(client):
    r=client.post("/api/tickets",json={"description":"My VPN is not connecting and authentication keeps failing."})
    assert r.status_code==201
    d=r.json()
    assert (d["intent"],d["category"],d["subcategory"],d["priority"],d["assigned_group"])==("Incident","Network","VPN","P2","Network Support")
    assert d["servicenow_reference"].startswith("MOCK-INC")
    assert client.get("/api/audit").json()["total"]>=1

def test_password_requires_auth_and_approval(client):
    assert client.post("/api/automation/execute",json={"issue":"My password has expired"}).json()["status"]=="blocked"
    assert client.post("/api/automation/execute",json={"issue":"My password has expired","authorized":True}).json()["status"]=="pending_approval"
    d=client.post("/api/automation/execute",json={"issue":"My password has expired","authorized":True,"approval_granted":True}).json()
    assert d["status"]=="completed" and d["validated"]
    assert "No real account" in d["message"]

def test_outlook_rag_sources(client):
    d=client.post("/api/chat",json={"message":"How do I troubleshoot Outlook synchronization?"}).json()
    assert d["intent"]=="Knowledge Question"
    assert len(d["sources"])>0
    assert "Outlook" in d["message"]

def test_vscode_provisioning(client):
    r=client.post("/api/software/requests",json={"software_id":"vscode"})
    assert r.status_code==201
    d=r.json()
    assert d["software_name"]=="Visual Studio Code" and d["status"]=="Completed"
    assert d["servicenow_reference"].startswith("MOCK-REQ")
    assert d["provisioning_result"]["mode"]=="mock_simulation"

def test_unknown_secret_refused(client):
    d=client.post("/api/chat",json={"message":"What is our confidential internal payroll database password?"}).json()
    assert "can't provide confidential credentials" in d["message"].lower()
    assert d["sources"]==[] and d["escalation_recommended"]

def test_idempotency(client):
    p={"description":"My VPN is not connecting","idempotency_key":"same"}
    assert client.post("/api/tickets",json=p).json()["id"]==client.post("/api/tickets",json=p).json()["id"]

def test_unknown_software(client):
    assert client.post("/api/software/requests",json={"software_id":"not-real"}).status_code==404

def test_action_allowlist(client):
    assert client.post("/api/automation/execute",json={"issue":"test","authorized":True,"approval_granted":True,"action":"shell"}).status_code==400

def test_input_validation(client):
    assert client.post("/api/chat",json={"message":"x"}).status_code==422
