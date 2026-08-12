"""
Registro de consultas — Nutri-OS · Fase 8

Añade una fila a datos/consultas.csv con lo que el plan ya sabe (paciente, edad,
protocolo, semanas, diagnósticos) más lo único que hay que teclear: el importe.

Local, sin Google Sheets: el sistema no depende de credenciales para nada.

Uso:
    python motor/registrar.py <carpeta_paciente> --costo 189 [--tipo seguimiento]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date

from comun import DIR_DATOS, DIR_PACIENTES

CABECERA = [
    "fecha", "paciente", "edad_meses", "tipo_consulta", "protocolo",
    "semanas_plan", "diagnosticos", "recetas_plan", "importe", "estado",
]
TIPOS = ("primera_vez", "plan", "seguimiento", "control")


def main() -> int:
    ap = argparse.ArgumentParser(description="Registra la consulta en el CSV local.")
    ap.add_argument("paciente")
    ap.add_argument("--costo", type=float, required=True, help="importe cobrado, en soles")
    ap.add_argument("--tipo", default="plan", choices=TIPOS)
    ap.add_argument("--fecha", default=None, help="YYYY-MM-DD; por defecto, la del plan")
    args = ap.parse_args()

    ruta_plan = DIR_PACIENTES / args.paciente / "plan.json"
    if not ruta_plan.exists():
        print(f"\n✗ No existe {ruta_plan}\n", file=sys.stderr)
        return 1

    plan = json.loads(ruta_plan.read_text(encoding="utf-8"))
    destino = DIR_DATOS / "consultas.csv"

    fila = [
        args.fecha or plan.get("fecha") or date.today().isoformat(),
        plan["paciente"],
        plan.get("edad_meses", ""),
        args.tipo,
        plan.get("protocolo", ""),
        len(plan["semanas"]),
        " | ".join(plan.get("diagnosticos") or []),
        len(plan.get("recetas_usadas") or []),
        f"{args.costo:.2f}",
        "entregado",
    ]

    # Si ya existe una fila de este paciente en esta fecha, se reemplaza:
    # regenerar un plan no debe duplicar el ingreso.
    filas: list[list[str]] = []
    if destino.exists():
        with destino.open(newline="", encoding="utf-8") as f:
            filas = [r for r in csv.reader(f)][1:]
        filas = [r for r in filas if not (r[:2] == [str(fila[0]), str(fila[1])])]

    filas.append([str(x) for x in fila])
    filas.sort(key=lambda r: r[0])

    with destino.open("w", newline="", encoding="utf-8") as f:
        # lineterminator="\n": csv.writer escribe CRLF por defecto y el archivo
        # está en LF, así que cada registro reescribía el CSV entero y el diff
        # salía con las 40 filas cambiadas para ver una consulta nueva.
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CABECERA)
        w.writerows(filas)

    print(f"✓ Registrado: {plan['paciente']} · {args.tipo} · S/ {args.costo:.2f}")
    print(f"  → {destino}   ({len(filas)} consulta(s) en total)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
