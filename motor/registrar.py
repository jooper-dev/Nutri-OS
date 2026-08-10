"""
Registro de consultas — Nutri-OS · Fase 7

Añade una fila a datos/consultas.csv. Local, sin Google Sheets: el sistema ya
no depende de credenciales OAuth para nada.

Uso:
    python motor/registrar.py <carpeta_paciente> --costo 189 [--tipo seguimiento]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date

from comun import DIR_DATOS, DIR_PACIENTES, ErrorNutriOS

CABECERA = ["fecha", "paciente", "tipo_consulta", "semanas_plan", "protocolo", "importe", "estado"]


def main() -> int:
    ap = argparse.ArgumentParser(description="Registra la consulta en el CSV local.")
    ap.add_argument("paciente")
    ap.add_argument("--costo", type=float, required=True, help="importe cobrado, en soles")
    ap.add_argument("--tipo", default="plan", help="plan | seguimiento | primera_vez")
    args = ap.parse_args()

    ruta_plan = DIR_PACIENTES / args.paciente / "plan.json"
    if not ruta_plan.exists():
        print(f"\n✗ No existe {ruta_plan}\n", file=sys.stderr)
        return 1

    plan = json.loads(ruta_plan.read_text(encoding="utf-8"))
    destino = DIR_DATOS / "consultas.csv"
    nuevo = not destino.exists()

    with destino.open("a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(CABECERA)
        w.writerow([
            plan.get("fecha") or date.today().isoformat(),
            plan["paciente"],
            args.tipo,
            len(plan["semanas"]),
            plan.get("protocolo", ""),
            f"{args.costo:.2f}",
            "entregado",
        ])

    print(f"✓ Registrado: {plan['paciente']} · S/ {args.costo:.2f}")
    print(f"  → {destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
