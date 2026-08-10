"""
Validador clínico — Nutri-OS · Fase 5

Vuelve a comprobar el plan ya ensamblado, sin confiar en el ensamblador.
Es deliberadamente independiente: lee el protocolo y la ficha por su cuenta y
recuenta todo desde cero. Si el motor tuviera un error, aquí se cae.

Sustituye a la antigua "Fase 4 · Self-QA", donde un modelo se auditaba a sí mismo.
Aquí no hay criterio ni interpretación: hay aritmética.

Salidas:
  ERROR   detiene el pipeline. Nada llega al PDF.
  AVISO   no detiene, pero aparece arriba del todo para que Paty lo lea.

Uso:
    python motor/validar.py <nombre_carpeta_paciente>
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from comun import (
    DIR_PACIENTES,
    ErrorNutriOS,
    cargar_alimentos_base,
    cargar_biblioteca,
    cargar_ficha,
    cargar_protocolo,
    normalizar,
)


class Reporte:
    def __init__(self) -> None:
        self.errores: list[str] = []
        self.avisos: list[str] = []

    def error(self, msg: str) -> None:
        self.errores.append(msg)

    def aviso(self, msg: str) -> None:
        self.avisos.append(msg)

    @property
    def ok(self) -> bool:
        return not self.errores


def _items(plan: dict):
    """Recorre todos los ítems del plan: (semana, dia, comida, item)."""
    for s in plan["semanas"]:
        for dia, comidas in s["dias"].items():
            for cid, comida in comidas.items():
                for item in comida["items"]:
                    yield s["semana"], dia, cid, item


def validar(nombre_carpeta: str) -> tuple[Reporte, dict]:
    carpeta = DIR_PACIENTES / nombre_carpeta
    ruta_plan = carpeta / "plan.json"
    if not ruta_plan.exists():
        raise ErrorNutriOS(f"No existe {ruta_plan}. Ejecuta antes motor/ensamblar.py")

    plan = json.loads(ruta_plan.read_text(encoding="utf-8"))
    ficha = cargar_ficha(carpeta)
    protocolo = cargar_protocolo(ficha["protocolo_sugerido"])
    recetas, avisos_bib = cargar_biblioteca()
    catalogo = {o.id: o for o in recetas + cargar_alimentos_base()}

    r = Reporte()
    for a in avisos_bib:
        r.aviso(f"Biblioteca: {a}")

    # --- 1. Coherencia paciente / plan -------------------------------------
    if plan.get("paciente") != ficha["paciente"]:
        r.error("El plan no corresponde a la ficha: los nombres de paciente no coinciden.")
    if plan.get("edad_meses") != ficha["edad_meses"]:
        r.error("La edad del plan no coincide con la de la ficha.")
    if len(plan["semanas"]) != int(ficha["semanas_plan"]):
        r.error(
            f"La ficha pide {ficha['semanas_plan']} semana(s) y el plan trae "
            f"{len(plan['semanas'])}."
        )

    # --- 2. Riesgo vital: alergias, rechazos y edad ------------------------
    alergias = {normalizar(a) for a in ficha.get("alergias") or []}
    rechazos = {normalizar(x) for x in ficha.get("rechazos") or []}

    for sem, dia, cid, item in _items(plan):
        ident = item.get("receta_id") or normalizar(item["nombre"])
        opcion = catalogo.get(ident) or next(
            (o for o in catalogo.values() if o.nombre == item["nombre"]), None
        )
        donde = f"S{sem} · {dia} · {cid}"

        if opcion is None:
            r.error(f"{donde}: «{item['nombre']}» no existe en la biblioteca ni en alimentos base.")
            continue

        choque = alergias & {normalizar(a) for a in opcion.alergenos}
        if choque:
            r.error(f"{donde}: «{item['nombre']}» contiene {', '.join(sorted(choque))} — ALERGIA declarada.")

        if normalizar(opcion.familia) in rechazos or normalizar(opcion.id) in rechazos:
            r.error(f"{donde}: «{item['nombre']}» está en la lista de rechazos.")

        if opcion.edad_min_meses > ficha["edad_meses"]:
            r.error(
                f"{donde}: «{item['nombre']}» exige {opcion.edad_min_meses} meses y "
                f"el paciente tiene {ficha['edad_meses']}."
            )

        if not item.get("cantidad"):
            r.error(f"{donde}: «{item['nombre']}» va sin cantidad (regla de cero orfandad).")
        elif "[" in str(item["cantidad"]) or "]" in str(item["cantidad"]):
            r.error(f"{donde}: la cantidad de «{item['nombre']}» conserva corchetes.")

    # --- 3. Frecuencias del protocolo, recontadas ---------------------------
    for s in plan["semanas"]:
        n = s["semana"]
        conteo_comp: Counter = Counter()
        conteo_fam: Counter = Counter()
        for dia, comidas in s["dias"].items():
            for cid, comida in comidas.items():
                for item in comida["items"]:
                    conteo_comp[(item["componente"], cid)] += 1
                    op = catalogo.get(item.get("receta_id") or "") or next(
                        (o for o in catalogo.values() if o.nombre == item["nombre"]), None
                    )
                    if op:
                        conteo_fam[(item["componente"], normalizar(op.familia), cid)] += 1

        for regla in protocolo.get("frecuencias_semanales") or []:
            if regla.get("cada_dias") or regla.get("modo") == "relleno":
                continue
            comp = regla["componente"]
            ambito = regla.get("en") or [c["id"] for c in protocolo["comidas"]]
            fam = regla.get("familia")
            veces = regla.get("veces")
            if veces is None:
                continue

            if fam:
                real = sum(conteo_fam[(comp, normalizar(fam), c)] for c in ambito)
                etiqueta = f"{comp}/{fam}"
            else:
                real = sum(conteo_comp[(comp, c)] for c in ambito)
                etiqueta = comp

            modo = regla.get("modo", "exacto")
            minimo = regla.get("minimo")
            degradada = any(etiqueta in d for d in plan.get("degradaciones", []))

            if modo == "exacto" and real != int(veces):
                (r.aviso if degradada else r.error)(
                    f"Semana {n}: {etiqueta} aparece {real} vez/veces; el protocolo exige "
                    f"exactamente {veces}." + (" (degradado por restricción del paciente)" if degradada else "")
                )
            elif modo == "maximo" and real > int(veces):
                r.error(f"Semana {n}: {etiqueta} aparece {real} veces; el máximo es {veces}.")
            elif modo == "minimo" and real < int(veces):
                r.error(f"Semana {n}: {etiqueta} aparece {real} veces; el mínimo es {veces}.")
            if minimo is not None and real < int(minimo) and not degradada:
                r.error(f"Semana {n}: {etiqueta} aparece {real} veces; el mínimo es {minimo}.")

    # --- 4. Reglas acopladas ------------------------------------------------
    for regla in protocolo.get("reglas_acopladas") or []:
        disp = regla["si"].split(".")[-1]
        obj = regla["entonces"].split(".")[-1]
        ambito = regla.get("ambito", "misma_comida")
        for s in plan["semanas"]:
            for dia, comidas in s["dias"].items():
                if ambito == "misma_comida":
                    for cid, comida in comidas.items():
                        comps = {i["componente"] for i in comida["items"]}
                        if disp in comps and obj not in comps:
                            r.error(
                                f"S{s['semana']} · {dia} · {cid}: hay {disp} sin {obj} "
                                f"({regla.get('razon', 'regla acoplada')})."
                            )
                else:
                    comps = {i["componente"] for c in comidas.values() for i in c["items"]}
                    if disp in comps and obj not in comps:
                        r.error(
                            f"S{s['semana']} · {dia}: hay {disp} sin {obj} en todo el día "
                            f"({regla.get('razon', 'regla acoplada')})."
                        )

    # --- 5. Variedad --------------------------------------------------------
    var = protocolo.get("variedad") or {}
    firmas: dict[str, str] = {}
    for s in plan["semanas"]:
        usos = Counter()
        for dia, comidas in s["dias"].items():
            firma = "|".join(
                f"{c}:" + ",".join(i["nombre"] for i in v["items"]) for c, v in sorted(comidas.items())
            )
            if var.get("no_repetir_dia_completo") and firma in firmas:
                r.error(
                    f"S{s['semana']} · {dia} repite exactamente el día {firmas[firma]}."
                )
            firmas[firma] = f"S{s['semana']} {dia}"
            for c in comidas.values():
                for i in c["items"]:
                    if i.get("receta_id"):
                        usos[i["receta_id"]] += 1

        tope = var.get("max_veces_misma_receta_semana")
        if tope:
            for rid, n_usos in usos.items():
                if n_usos > int(tope):
                    r.error(f"Semana {s['semana']}: la receta «{rid}» aparece {n_usos} veces (tope {tope}).")

        minimo = var.get("min_recetas_distintas_semana")
        if minimo and len(usos) < int(minimo):
            r.aviso(
                f"Semana {s['semana']}: solo {len(usos)} recetas distintas del recetario "
                f"(el protocolo sugiere {minimo}). La biblioteca necesita crecer."
            )

    # --- 6. Recetas sin validar en cocina -----------------------------------
    sin_probar = [
        rid for rid in plan.get("recetas_usadas", [])
        if rid in catalogo and catalogo[rid].es_receta and not catalogo[rid].validada_en_cocina
    ]
    if sin_probar:
        r.aviso(
            f"{len(sin_probar)} receta(s) del plan no están marcadas como probadas en cocina: "
            + ", ".join(sin_probar)
        )

    # --- 7. Degradaciones del ensamblador -----------------------------------
    for d in plan.get("degradaciones", []):
        r.aviso(f"Sustitución forzada: {d}")

    return r, plan


def escribir_reporte(carpeta: Path, r: Reporte, plan: dict) -> Path:
    lineas = [
        f"# Reporte de validación — {plan.get('paciente','?')}",
        "",
        f"Protocolo: {plan.get('protocolo_nombre','?')}  ·  "
        f"{len(plan['semanas'])} semana(s)  ·  fecha {plan.get('fecha','')}",
        "",
        "## Resultado",
        "",
        "**APTO PARA REVISIÓN** — sin errores bloqueantes."
        if r.ok
        else f"**BLOQUEADO** — {len(r.errores)} error(es). El plan no debe renderizarse.",
        "",
    ]
    if r.errores:
        lineas += ["## Errores", ""] + [f"- {e}" for e in r.errores] + [""]
    if r.avisos:
        lineas += ["## Avisos", ""] + [f"- {a}" for a in r.avisos] + [""]
    if not r.errores and not r.avisos:
        lineas += ["Sin avisos.", ""]
    lineas += [
        "---",
        "",
        "Este reporte lo genera código, no un modelo de lenguaje: los conteos son "
        "aritmética sobre el plan ya construido. Un error aquí siempre es real.",
        "",
        "Revisión final y firma clínica: Nut. Patricia López.",
    ]
    destino = carpeta / "reporte_qa.md"
    destino.write_text("\n".join(lineas), encoding="utf-8")
    return destino


def main() -> int:
    ap = argparse.ArgumentParser(description="Valida el plan ensamblado de un paciente.")
    ap.add_argument("paciente")
    args = ap.parse_args()

    try:
        r, plan = validar(args.paciente)
    except ErrorNutriOS as e:
        print(f"\n✗ {e}\n", file=sys.stderr)
        return 2

    destino = escribir_reporte(DIR_PACIENTES / args.paciente, r, plan)

    for e in r.errores:
        print(f"  ✗ {e}")
    for a in r.avisos:
        print(f"  ⚠ {a}")
    print()
    if r.ok:
        print(f"✓ Plan válido. {len(r.avisos)} aviso(s) para revisar.")
    else:
        print(f"✗ Plan BLOQUEADO: {len(r.errores)} error(es).")
    print(f"  → {destino}")
    return 0 if r.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
