# Clin come servizio per agenti su server (vedi deploy/README.md).
# Solo regole e OCR, nessun modello di rete: GLiNER si puo' aggiungere come servizio a parte.
FROM python:3.12-slim

RUN pip install --no-cache-dir PyMuPDF==1.28.0 openpyxl==3.1.5 cryptography==48.0.0 \
 && useradd --system --uid 10001 --home-dir /nonexistent clin

WORKDIR /opt/clin
COPY anonymize_engine.py clin.py clin_api.py clin_guard.py clin_lingue.py clin_llm.py clin_mcp.py clin_ner.py \
     clin_ocr.py clin_results.py clin_sanitario.py clin_settings.py clin_text.py tabular_engine.py ./
COPY scripts/fetch_ocr_model.py scripts/
# modello OCR italiano (2,6 MB), scaricato e verificato con SHA-256 durante la costruzione dell'immagine
RUN python scripts/fetch_ocr_model.py --dest /opt/clin/tessdata

ENV CLIN_TESSDATA=/opt/clin/tessdata \
    CLIN_DATI=/dati_clin \
    CLIN_LLM=0 \
    PYTHONDONTWRITEBYTECODE=1
# tabelle di corrispondenza e registro: solo in questo volume, che nessun altro container monta
VOLUME ["/dati_clin"]
USER clin
EXPOSE 8765
HEALTHCHECK CMD python -c "import socket; socket.create_connection(('127.0.0.1', 8765), 2)"
CMD ["python", "clin.py", "servizio", "--host", "0.0.0.0", "--porta", "8765"]
