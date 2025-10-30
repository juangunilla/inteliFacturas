import json
import os

DATA_DIR=os.path.join(os.path.dirname(__file__),"data")
JSON_PATH=os.path.join(DATA_DIR,"facturas.json")

def _ensure_dir():
 os.makedirs(DATA_DIR,exist_ok=True)

def load_records():
 if not os.path.exists(JSON_PATH):
  return []
 try:
  with open(JSON_PATH,"r",encoding="utf-8") as fh:
   data=json.load(fh)
   return data if isinstance(data,list) else []
 except json.JSONDecodeError:
  return []

def _save_records(records):
 _ensure_dir()
 tmp_path=JSON_PATH+".tmp"
 with open(tmp_path,"w",encoding="utf-8") as fh:
  json.dump(records,fh,ensure_ascii=False,indent=2)
 os.replace(tmp_path,JSON_PATH)

def upsert_record(record):
 record_id=record.get("id")
 if not record_id:
  raise ValueError("record must include non-empty id")
 records=load_records()
 for idx,existing in enumerate(records):
  if existing.get("id")==record_id:
   merged=dict(existing)
   merged.update(record)
   records[idx]=merged
   break
 else:
  records.append(record)
 _save_records(records)
 return record

def get_record(record_id):
 if not record_id:
  return None
 for record in load_records():
  if record.get("id")==record_id:
   return record
 return None
