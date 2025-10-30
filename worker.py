import os, redis, base64, tempfile, re, openpyxl, json
from paddleocr import PaddleOCR
from pdf2image import convert_from_path
from datetime import datetime, timezone
import storage

REDIS_HOST = os.getenv("REDIS_HOST", "redis")
r = redis.Redis(host=REDIS_HOST, decode_responses=False)

# OCR actualizado (sin angle_cls, sin cls=True)
ocr = PaddleOCR(lang='es', use_textline_orientation=True)

def _iso_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00","Z")

def run(path):
    out = []
    for line in ocr.ocr(path):  
        for _, tx in line:
            out.append(tx[0])
    return out

def extra(t):
    j = " ".join(t)
    mt = re.search(r"(Factura|Nota de Crédito)\s+([ABC])", j, re.I)
    tipo = mt.group(2).upper() if mt else None
    nota = "SI" if re.search(r"Nota de Crédito", j, re.I) else "NO"

    f = re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", j)
    neto = re.search(r"(Neto|Subtotal).*?(\$ ?\d[\d\.,]+)", j, re.I)
    ng = re.search(r"(No Gravado).*?(\$ ?\d[\d\.,]+)", j, re.I)
    iva = re.search(r"(IVA).*?(\$ ?\d[\d\.,]+)", j, re.I)
    tot = re.search(r"(Importe Total|Total).*?(\$ ?\d[\d\.,]+)", j, re.I)
    comp = re.search(r"\b\d{4}-\d{6,8}\b", j)
    locs = re.findall(r"Domicilio.*?([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+)", j)
    loc = locs[1] if len(locs) > 1 else None

    return {
        "fecha": f.group(0) if f else None,
        "tipo": tipo,
        "nro": comp.group(0) if comp else None,
        "neto": neto.group(2) if neto else None,
        "ng": ng.group(2) if ng else None,
        "iva": iva.group(2) if iva else None,
        "total": tot.group(2) if tot else None,
        "loc": loc,
        "nota": nota
    }

def save_xlsx(d):
    os.makedirs("data", exist_ok=True)
    fn = "data/facturas.xlsx"

    if os.path.exists(fn):
        wb = openpyxl.load_workbook(fn)
    else:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Facturas"
        ws.append(["Fecha","Tipo","Nro","Neto","NoGrav","IVA","Total","Loc","Nota"])

    ws = wb["Facturas"]
    ws.append([d["fecha"], d["tipo"], d["nro"], d["neto"], d["ng"], d["iva"], d["total"], d["loc"], d["nota"]])
    wb.save(fn)

def process_job(raw_payload):
    payload = json.loads(raw_payload.decode("utf-8"))
    file_id = payload["id"]

    storage.upsert_record({"id": file_id, "status": "processing", "started_at": _iso_now()})
    
    try:
        data = base64.b64decode(payload["data"])
        ext = os.path.splitext(payload.get("filename",""))[1].lower()
        if ext != ".pdf" and data.startswith(b"%PDF"): ext = ".pdf"
        tmp_name = "source" + ext if ext else "source"

        with tempfile.TemporaryDirectory() as tmp:
            p = os.path.join(tmp, tmp_name)
            open(p, "wb").write(data)

            if ext == ".pdf":
                pages = convert_from_path(p)
                text = []
                for i, page in enumerate(pages):
                    img = os.path.join(tmp, f"p{i}.png")
                    page.save(img, "PNG")
                    text += run(img)
            else:
                text = run(p)

        d = extra(text)
        save_xlsx(d)

        storage.upsert_record({
            "id": file_id,
            "status": "processed",
            "processed_at": _iso_now(),
            **d,
            "error": None
        })

    except Exception as exc:
        storage.upsert_record({
            "id": file_id,
            "status": "failed",
            "processed_at": _iso_now(),
            "error": str(exc)
        })
        print(f"Error procesando factura {file_id}: {exc}", flush=True)

while True:
    job = r.brpop("facturas")
    process_job(job[1])
