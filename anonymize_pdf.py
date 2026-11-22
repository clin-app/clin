#!/usr/bin/env python3
"""
Clin - Interfaccia a riga di comando.

Anonimizza un singolo PDF o un'intera cartella usando lo stesso motore della
GUI (`anonymize_engine`). Nessun dato personale e' codificato nel sorgente:
i nominativi da oscurare vanno passati con `--targets` oppure con
`--targets-file`.

Esempi
------
    python3 anonymize_pdf.py referto.pdf referto_anon.pdf
    python3 anonymize_pdf.py ./Referti ./Anonimizzati
    python3 anonymize_pdf.py in.pdf out.pdf --targets "MARIO ROSSI" 04/05/2020
    python3 anonymize_pdf.py ./in ./out --targets-file nomi.txt --keep-labels
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List

from anonymize_engine import (
    MAX_LEVEL,
    BatchResult,
    anonymize_document,
    parse_lines_exact,
    parse_text_lines,
    process_batch_files,
)

FILL_COLORS = {
    "nero": (0.0, 0.0, 0.0),
    "bianco": (1.0, 1.0, 1.0),
    "grigio": (0.5, 0.5, 0.5),
}


def _read_list_file(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SystemExit(f"Impossibile leggere {path}: {exc}")


def _print_result(res, verbose: bool) -> None:
    name = res.input_path.name
    if res.error:
        print(f"  ERRORE  {name}: {res.error}", file=sys.stderr)
        return
    print(f"  OK      {name} -> {res.output_path.name} ({res.redactions} oscuramenti)")
    for w in res.warnings:
        print(f"          Avviso: {w}")
    if verbose and res.per_category:
        for cat, n in sorted(res.per_category.items(), key=lambda kv: -kv[1]):
            print(f"            - {cat}: {n}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Anonimizzatore PDF per documenti sanitari (Clin): rimuove sempre tutti i dati personali",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("input_path", help="File PDF o cartella di input")
    parser.add_argument("output_path", help="File PDF o cartella di output")
    parser.add_argument(
        "--targets", "-t", nargs="*", default=[],
        help="Termini da oscurare sempre (nomi, date, codici)",
    )
    parser.add_argument(
        "--targets-file", type=Path,
        help="File di testo con un termine da oscurare per riga",
    )
    parser.add_argument(
        "--whitelist", "-w", nargs="*", default=[],
        help="Termini da non oscurare mai",
    )
    parser.add_argument(
        "--whitelist-file", type=Path,
        help="File di testo con un termine da preservare per riga",
    )
    parser.add_argument(
        "--keep-images", action="store_true",
        help="Mantiene loghi ed immagini invece di rimuoverli",
    )
    parser.add_argument(
        "--keep-labels", action="store_true",
        help="Oscura solo il valore, lasciando visibile l'etichetta (es. \"Paziente:\")",
    )
    parser.add_argument(
        "--keep-metadata", action="store_true",
        help="Non ripulisce metadati, allegati e annotazioni del PDF",
    )
    parser.add_argument(
        "--color", choices=sorted(FILL_COLORS), default="nero",
        help="Colore dei rettangoli di oscuramento (default: nero)",
    )
    parser.add_argument(
        "--no-overwrite", action="store_true",
        help="Non sovrascrive i file di output gia' esistenti",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Dettaglio per categoria")
    return parser


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    raw_targets = "\n".join(args.targets)
    if args.targets_file:
        raw_targets += "\n" + _read_list_file(args.targets_file)
    raw_whitelist = "\n".join(args.whitelist)
    if args.whitelist_file:
        raw_whitelist += "\n" + _read_list_file(args.whitelist_file)

    explicit = parse_text_lines(raw_targets)
    whitelist = parse_lines_exact(raw_whitelist)

    common = dict(
        sensitivity_level=MAX_LEVEL,
        remove_images=not args.keep_images,
        explicit_targets=explicit,
        whitelist_words=whitelist,
        fill_color=FILL_COLORS[args.color],
        keep_labels=args.keep_labels,
        sanitize_metadata=not args.keep_metadata,
    )

    inp = Path(args.input_path)
    outp = Path(args.output_path)

    if inp.is_file():
        res = anonymize_document(inp, outp, **common)
        _print_result(res, args.verbose)
        return 1 if res.error else 0

    if inp.is_dir():
        pdf_files = sorted(inp.glob("*.pdf"))
        print(f"Trovati {len(pdf_files)} file PDF in {inp}")
        batch = BatchResult()
        process_batch_files(
            file_list=pdf_files,
            output_dir=outp,
            progress_callback=None,
            overwrite=not args.no_overwrite,
            result_callback=lambda r: _print_result(r, args.verbose),
            batch_result=batch,
            **common,
        )
        print(
            f"\nCompletato: {batch.processed} file elaborati, "
            f"{batch.total_redactions} oscuramenti totali."
        )
        if batch.failed:
            print(f"{len(batch.failed)} file non elaborati.", file=sys.stderr)
            return 1
        return 0

    print(f"Percorso non valido: {inp}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
