from flask import Flask,request,jsonify,send_file,send_from_directory,abort
from werkzeug.utils import secure_filename
import os,redis,base64,json,uuid
from datetime import datetime,timezone
import storage

REDIS_HOST=os.getenv("REDIS_HOST","localhost")
r=redis.Redis(host=REDIS_HOST,decode_responses=False)
app=Flask(__name__)
DATA_DIR=os.path.join(os.path.dirname(__file__),"data")
UPLOAD_DIR=os.path.join(DATA_DIR,"files")
os.makedirs(UPLOAD_DIR,exist_ok=True)

def _iso_now():
 return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")

def _queue_file(file_storage):
 filename=file_storage.filename or "factura"
 safe=secure_filename(filename) or "factura"
 file_id=uuid.uuid4().hex
 stored_name=f"{file_id}_{safe}"
 data=file_storage.read()
 with open(os.path.join(UPLOAD_DIR,stored_name),"wb") as fh:
  fh.write(data)
 payload=json.dumps({
  "id":file_id,
  "filename":filename,
  "stored_name":stored_name,
  "data":base64.b64encode(data).decode("ascii")
 })
 r.lpush("facturas",payload)
 storage.upsert_record({
  "id":file_id,
  "filename":filename,
  "stored_name":stored_name,
  "status":"queued",
  "created_at":_iso_now(),
  "processed_at":None
 })
 return {"id":file_id,"filename":filename}

@app.get("/")
def index(): return open("index.html").read()

@app.post("/enqueue")
def enqueue():
 f=request.files.get("file")
 if not f: return {"err":"no file"},400
 res=_queue_file(f)
 return {"ok":True,"id":res["id"]}

@app.post("/api/upload")
def upload_bulk():
 files=request.files.getlist("files")
 if not files: return {"error":"ningún archivo recibido"},400
 results=[]
 for f in files:
  results.append(_queue_file(f))
 return {"queued":len(results),"items":results}

@app.get("/api/invoices")
def list_invoices():
 records=storage.load_records()
 sorted_records=sorted(records,key=lambda rec:rec.get("created_at") or "",reverse=True)
 items=[]
 for rec in sorted_records:
  item=dict(rec)
  if rec.get("id") and rec.get("stored_name"):
   item["download_url"]=f"/api/invoices/{rec['id']}/download"
  else:
   item["download_url"]=None
  items.append(item)
 return jsonify({"items":items})

@app.get("/api/invoices/<invoice_id>/download")
def download_invoice(invoice_id):
 record=storage.get_record(invoice_id)
 if not record or not record.get("stored_name"):
  abort(404)
 stored_name=record["stored_name"]
 path=os.path.join(UPLOAD_DIR,stored_name)
 if not os.path.exists(path):
  abort(404)
 download_name=record.get("filename") or stored_name
 return send_from_directory(UPLOAD_DIR,stored_name,as_attachment=True,download_name=download_name)

@app.get("/api/export/excel")
def download_excel():
 excel_path=os.path.join(DATA_DIR,"facturas.xlsx")
 if not os.path.exists(excel_path):
  abort(404)
 return send_file(excel_path,as_attachment=True,download_name="facturas.xlsx")

app.run(host="0.0.0.0",port=5000)
