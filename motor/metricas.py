"""
Métricas — Nutri-OS

Lee datos/consultas.csv y resume el mes: cuántas consultas, cuánto se facturó,
ticket promedio y de qué tipo fueron. Sin gráficos ni dependencias: números que
se leen en diez segundos.

Uso:
    python motor/metricas.py                 mes en curso
    python motor/metricas.py --mes 2026-07   un mes concreto
    python motor/metricas.py --todo          histórico por meses
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter, defaultdict
from datetime import date

from comun import DIR_DATOS


def cargar() -> list[dict]:
    ruta = DIR_DATOS / "consultas.csv"
    if not ruta.exists():
        return []
    with ruta.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def importe(r: dict) -> float:
    try:
        return float(r.get("importe") or 0)
    except ValueError:
        return 0.0


def resumen(filas: list[dict], titulo: str) -> None:
    if not filas:
        print(f"\n{titulo}: sin consultas registradas.")
        return

    total = sum(importe(r) for r in filas)
    n = len(filas)
    print(f"\n— {titulo} —\n")
    print(f"  Consultas           {n}")
    print(f"  Facturado           S/ {total:,.2f}")
    print(f"  Ticket promedio     S/ {total / n:,.2f}")

    por_tipo = Counter(r.get("tipo_consulta", "") for r in filas)
    print("\n  Por tipo")
    for t, c in por_tipo.most_common():
        sub = sum(importe(r) for r in filas if r.get("tipo_consulta") == t)
        print(f"    {t or '(sin tipo)':<16} {c:>3}   S/ {sub:,.2f}")

    dx = Counter(
        d.strip()
        for r in filas
        for d in (r.get("diagnosticos") or "").split("|")
        if d.strip() and d.strip() != "ninguno"
    )
    if dx:
        print("\n  Motivos más frecuentes")
        for d, c in dx.most_common(5):
            print(f"    {d:<16} {c:>3}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Resumen de consultas.")
    ap.add_argument("--mes", default=None, help="YYYY-MM")
    ap.add_argument("--todo", action="store_true", help="histórico mes a mes")
    args = ap.parse_args()

    filas = cargar()
    if not filas:
        print("\nNo hay consultas registradas todavía.")
        print("  Se añaden con:  python motor/registrar.py <paciente> --costo <importe>\n")
        return 0

    if args.todo:
        meses: dict[str, list[dict]] = defaultdict(list)
        for r in filas:
            meses[str(r.get("fecha", ""))[:7]].append(r)
        for m in sorted(meses):
            resumen(meses[m], m)
        total = sum(importe(r) for r in filas)
        print(f"\n  ACUMULADO: {len(filas)} consultas · S/ {total:,.2f}\n")
        return 0

    mes = args.mes or date.today().strftime("%Y-%m")
    resumen([r for r in filas if str(r.get("fecha", "")).startswith(mes)], mes)
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
