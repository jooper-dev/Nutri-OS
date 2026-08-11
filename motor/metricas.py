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

from pathlib import Path

from comun import DIR_DATOS, DIR_SALIDAS


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


HTML_BASE = """<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<title>Métricas · GrowKids</title><style>
:root{--crema:#FBF8F3;--cobre:#B0714A;--azul:#24374E;--tenue:#8A8078;--linea:#E4DCD1}
*{box-sizing:border-box}
body{margin:0;padding:40px 24px;background:var(--crema);color:#2E2A26;
 font-family:Inter,-apple-system,"Segoe UI",Roboto,sans-serif;line-height:1.5}
.wrap{max-width:860px;margin:0 auto}
.marca{font-size:11px;letter-spacing:.3em;text-transform:uppercase;color:var(--cobre)}
h1{font-size:30px;color:var(--azul);margin:6px 0 2px}
.sub{color:var(--tenue);margin-bottom:32px}
.tarjetas{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:38px}
.t{background:#fff;border:1px solid var(--linea);border-radius:10px;padding:18px 20px}
.t .k{font-size:10px;letter-spacing:.14em;text-transform:uppercase;color:var(--tenue)}
.t .v{font-size:27px;color:var(--azul);margin-top:6px;font-weight:600}
h2{font-size:13px;letter-spacing:.16em;text-transform:uppercase;color:var(--cobre);
 margin:34px 0 12px;font-weight:600}
table{width:100%;border-collapse:collapse;background:#fff;
 border:1px solid var(--linea);border-radius:10px;overflow:hidden}
th{text-align:left;font-size:11px;letter-spacing:.1em;text-transform:uppercase;
 color:var(--tenue);font-weight:600;padding:11px 16px;background:#F4EFE7}
td{padding:11px 16px;border-top:1px solid var(--linea);font-size:14px}
td.n{text-align:right;color:var(--azul);font-variant-numeric:tabular-nums}
.barra{height:6px;background:var(--cobre);border-radius:3px;min-width:3px}
footer{margin-top:42px;padding-top:16px;border-top:1px solid var(--linea);
 font-size:12px;color:var(--tenue)}
</style></head><body><div class="wrap">{cuerpo}</div></body></html>"""


def escribir_html(filas: list[dict]) -> Path:
    from datetime import datetime
    from html import escape

    meses: dict[str, list[dict]] = defaultdict(list)
    for r in filas:
        meses[str(r.get("fecha", ""))[:7]].append(r)
    orden = sorted(meses, reverse=True)
    actual = orden[0] if orden else date.today().strftime("%Y-%m")
    del_mes = meses.get(actual, [])
    total_mes = sum(importe(r) for r in del_mes)

    p: list[str] = []
    p.append('<div class="marca">GrowKids · Nut. Patricia López</div>')
    p.append("<h1>Métricas de consulta</h1>")
    p.append(f'<div class="sub">Mes en curso: {escape(actual)} · '
             f'{len(filas)} consulta(s) registradas en total</div>')

    def tarjeta(k: str, v: str) -> str:
        return f'<div class="t"><div class="k">{k}</div><div class="v">{v}</div></div>'

    p.append('<div class="tarjetas">')
    p.append(tarjeta("Consultas del mes", str(len(del_mes))))
    p.append(tarjeta("Facturado", f"S/ {total_mes:,.0f}"))
    p.append(tarjeta("Ticket promedio",
                     f"S/ {total_mes / len(del_mes):,.0f}" if del_mes else "—"))
    edades = [int(r["edad_meses"]) for r in del_mes if str(r.get("edad_meses", "")).isdigit()]
    p.append(tarjeta("Edad media", f"{sum(edades) // len(edades) // 12} años" if edades else "—"))
    p.append("</div>")

    if len(orden) > 1:
        tope = max(sum(importe(r) for r in meses[m]) for m in orden) or 1
        p.append("<h2>Evolución mensual</h2><table>")
        p.append("<tr><th>Mes</th><th></th><th>Consultas</th><th>Facturado</th></tr>")
        for m in orden:
            t = sum(importe(r) for r in meses[m])
            ancho = max(3, round(t / tope * 100))
            p.append(f'<tr><td>{escape(m)}</td>'
                     f'<td style="width:45%"><div class="barra" style="width:{ancho}%"></div></td>'
                     f'<td class="n">{len(meses[m])}</td>'
                     f'<td class="n">S/ {t:,.2f}</td></tr>')
        p.append("</table>")

    if del_mes:
        p.append("<h2>Por tipo de consulta</h2><table>")
        p.append("<tr><th>Tipo</th><th>Consultas</th><th>Facturado</th></tr>")
        for t, c in Counter(r.get("tipo_consulta", "") for r in del_mes).most_common():
            sub = sum(importe(r) for r in del_mes if r.get("tipo_consulta") == t)
            p.append(f'<tr><td>{escape(t or "(sin tipo)")}</td>'
                     f'<td class="n">{c}</td><td class="n">S/ {sub:,.2f}</td></tr>')
        p.append("</table>")

        dx = Counter(
            d.strip() for r in del_mes
            for d in (r.get("diagnosticos") or "").split("|")
            if d.strip() and d.strip() != "ninguno"
        )
        if dx:
            p.append("<h2>Motivos de consulta</h2><table>")
            p.append("<tr><th>Motivo</th><th>Casos</th></tr>")
            for d, c in dx.most_common():
                p.append(f"<tr><td>{escape(d)}</td><td class='n'>{c}</td></tr>")
            p.append("</table>")

        p.append("<h2>Detalle del mes</h2><table>")
        p.append("<tr><th>Fecha</th><th>Paciente</th><th>Tipo</th><th>Semanas</th><th>Importe</th></tr>")
        for r in sorted(del_mes, key=lambda x: x.get("fecha", ""), reverse=True):
            p.append(f'<tr><td>{escape(str(r.get("fecha","")))}</td>'
                     f'<td>{escape(str(r.get("paciente","")))}</td>'
                     f'<td>{escape(str(r.get("tipo_consulta","")))}</td>'
                     f'<td class="n">{escape(str(r.get("semanas_plan","")))}</td>'
                     f'<td class="n">S/ {importe(r):,.2f}</td></tr>')
        p.append("</table>")

    p.append(f"<footer>Generado el {datetime.now():%d/%m/%Y %H:%M} desde "
             f"datos/consultas.csv · Nutri-OS</footer>")

    destino = DIR_SALIDAS / "metricas.html"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(HTML_BASE.replace("{cuerpo}", "\n".join(p)), encoding="utf-8")
    return destino


def main() -> int:
    ap = argparse.ArgumentParser(description="Resumen de consultas.")
    ap.add_argument("--mes", default=None, help="YYYY-MM")
    ap.add_argument("--todo", action="store_true", help="histórico mes a mes")
    ap.add_argument("--html", action="store_true", help="genera salidas/metricas.html para abrir en el navegador")
    args = ap.parse_args()

    filas = cargar()
    if not filas:
        print("\nNo hay consultas registradas todavía.")
        print("  Se añaden con:  python motor/registrar.py <paciente> --costo <importe>\n")
        return 0

    if args.html:
        destino = escribir_html(filas)
        print(f"\n✓ Panel generado.\n  → {destino}\n  Ábrelo con doble clic.\n")
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
