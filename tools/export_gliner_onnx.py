"""
Esporta GLiNER (urchade/gliner_multi_pii-v1) in ONNX per l'estensione del browser.

Si comprime solo la tabella dei vocaboli (Gather, int8): 581 MB invece di 1,16 GB, con
risultati identici al modello originale (99,6% delle entita' sul benchmark). La
quantizzazione int8 completa (349 MB) peggiora molto il riconoscimento e non si usa.

    PYTHONPATH=<onnx, onnxruntime> ~/.clin/ner/bin/python tools/export_gliner_onnx.py ~/.clin/modelli/gliner-onnx
"""
import shutil
import sys
import tempfile
from pathlib import Path

from gliner import GLiNER
from onnxruntime.quantization import QuantType, quantize_dynamic

out = Path(sys.argv[1] if len(sys.argv) > 1 else "~/.clin/modelli/gliner-onnx").expanduser()
out.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory() as tmp:
    GLiNER.from_pretrained("urchade/gliner_multi_pii-v1").export_to_onnx(tmp, quantize=False)
    quantize_dynamic(f"{tmp}/model.onnx", str(out / "model.onnx"), op_types_to_quantize=["Gather"],
                     weight_type=QuantType.QUInt8)
    for f in ("tokenizer.json", "tokenizer_config.json", "gliner_config.json"):
        shutil.copy2(Path(tmp) / f, out / f)
print(f"Modello ONNX in {out}")
