import hashlib, math, re
from pathlib import Path
from .core.config import get_settings
from .storage import get_store
from .audit import record_event

TOKEN_RE=re.compile(r"[a-zA-Z0-9][a-zA-Z0-9._+-]*")
def tokens(text): return [t.lower() for t in TOKEN_RE.findall(text)]
def stable_hash(s): return int(hashlib.sha256(s.encode()).hexdigest()[:12],16)
def offline_embed(text,dim=384):
    """Deterministic feature-hash embedding for offline demos, not a transformer model."""
    v=[0.0]*dim; ts=tokens(text)
    for t in ts: v[stable_hash(t)%dim]+=1
    for i in range(len(ts)-1): v[stable_hash(ts[i]+"_"+ts[i+1])%dim]+=.45
    n=math.sqrt(sum(x*x for x in v)) or 1
    return [x/n for x in v]
def cosine(a,b):
    d=(math.sqrt(sum(x*x for x in a))*math.sqrt(sum(x*x for x in b))) or 1
    return sum(x*y for x,y in zip(a,b))/d
def chunk_text(text,size=650,overlap=100):
    clean=re.sub(r"\\s+"," ",text).strip()
    if not clean:return []
    out=[]; start=0
    while start<len(clean):
        end=min(start+size,len(clean));out.append(clean[start:end])
        if end==len(clean):break
        start=max(end-overlap,start+1)
    return out

class KnowledgeService:
    def __init__(self):
        self.settings=get_settings();self.chunks=[];self.embedder=None
        if self.settings.embedding_mode=="sentence-transformers":
            try:
                from sentence_transformers import SentenceTransformer
                self.embedder=SentenceTransformer(self.settings.embedding_model)
            except Exception: self.embedder=None
    def embed(self,text):
        return self.embedder.encode(text,normalize_embeddings=True).tolist() if self.embedder is not None else offline_embed(text)
    def ingest_directory(self,directory=None):
        root=Path(__file__).resolve().parents[2]
        directory=directory or root/"knowledge_base"; docs=[]
        for path in sorted(directory.glob("*.md")):
            text=path.read_text(encoding="utf-8")
            title=next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")),path.stem)
            approved="approval_status: approved" in text.lower()
            if not approved:continue
            aid=path.stem.upper().replace("-","_")
            for i,chunk in enumerate(chunk_text(text)):
                docs.append({"article_id":aid,"title":title,"category":path.stem.split("-",1)[0].title(),
                    "version":"1.0","approved":True,"chunk_id":f"{aid}-{i}","text":chunk,
                    "embedding":self.embed(chunk),"source_file":path.name})
        self.chunks=docs; store=get_store()
        if hasattr(store,"_path"): store._path("knowledge").write_text("[]",encoding="utf-8")
        for d in docs: store.insert("knowledge",{k:v for k,v in d.items() if k not in ("embedding","text")})
        record_event("system","knowledge_ingest","success",details={"documents":len(set(d["article_id"] for d in docs)),"chunks":len(docs),"embedding_mode":self.settings.embedding_mode})
        return {"documents":len(set(d["article_id"] for d in docs)),"chunks":len(docs),"embedding_mode":self.settings.embedding_mode,"vector_db_mode":"local"}
    def search(self,query,top_k=4):
        if not self.chunks:self.ingest_directory()
        q=self.embed(query); scored=sorted(((cosine(q,d["embedding"]),d) for d in self.chunks if d["approved"]),key=lambda x:x[0],reverse=True)
        output=[];seen=set()
        for score,d in scored:
            if score<self.settings.rag_relevance_threshold or d["article_id"] in seen:continue
            seen.add(d["article_id"]);output.append({"article_id":d["article_id"],"title":d["title"],"category":d["category"],"score":round(float(score),4),"excerpt":d["text"][:420]})
            if len(output)>=top_k:break
        return output
    def answer(self,query,top_k=4):
        sources=self.search(query,top_k)
        if not sources:return {"answer":"I could not find sufficient evidence in the approved IT knowledge base to answer that reliably. Please contact the helpdesk or create a ticket.","sources":[],"grounded":False}
        excerpts="\\n\\n".join(f"From {s['title']}: {s['excerpt']}" for s in sources[:2])
        return {"answer":"Based on approved knowledge articles, review these steps:\\n\\n"+excerpts+"\\n\\nIf the issue continues, contact the helpdesk.","sources":sources,"grounded":True}
