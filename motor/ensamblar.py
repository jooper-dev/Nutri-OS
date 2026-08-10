"""
Ensamblador de planes — Nutri-OS · Fase 4

Convierte (protocolo + ficha del paciente + biblioteca) en un plan completo.

Principio: las frecuencias del protocolo se garantizan POR CONSTRUCCIÓN.
No se generan menús para después revisarlos: se reservan primero las ranuras
que las reglas exigen y solo después se rellena el resto. Un plan que viole
una frecuencia es un fallo del motor, no un descuido — y el validador lo para.

Uso:
    python motor/ensamblar.py <nombre_carpeta_paciente> [--semilla N]
"""

from __future__ import annotations

import argparse
import math
import random
import sys
from collections import defaultdict
from pathlib import Path

from comun import (
    DIAS,
    DIR_PACIENTES,
    ErrorNutriOS,
    Opcion,
    cargar_alimentos_base,
    cargar_biblioteca,
    cargar_ficha,
    cargar_protocolo,
    guardar_json,
    normalizar,
)

MAX_INTENTOS = 60


# ---------------------------------------------------------------------------
# Selección de opciones
# ---------------------------------------------------------------------------


class Repertorio:
    """Todas las opciones disponibles, ya filtradas para este paciente."""

    def __init__(self, opciones: list[Opcion], ficha: dict, protocolo: dict):
        self.ficha = ficha
        self.descartes: list[tuple[str, str]] = []
        self.por_componente: dict[str, list[Opcion]] = defaultdict(list)

        for o in opciones:
            apta, motivo = o.apta_para(ficha)
            if apta:
                self.por_componente[o.componente].append(o)
            else:
                self.descartes.append((o.nombre, motivo))

        # Familias con cupo propio en el protocolo: no pueden usarse como
        # relleno improvisado, o se desbordaría su frecuencia.
        self.reguladas = {
            normalizar(r["familia"])
            for r in (protocolo.get("frecuencias_semanales") or [])
            if r.get("familia") and r.get("modo") != "relleno"
        }
        prefs = (protocolo.get("preferencias_clinicas") or {})
        self.priorizar: set[str] = set()
        for dx in ficha.get("diagnosticos") or []:
            self.priorizar |= set((prefs.get(dx) or {}).get("priorizar_aporta") or [])

    def candidatas(self, componente: str, comida: str, familia: str = "") -> list[Opcion]:
        salida = []
        for o in self.por_componente.get(componente, []):
            if familia and normalizar(o.familia) != normalizar(familia):
                continue
            # Una receta solo entra en los momentos que declara.
            if o.es_receta and o.momento and comida not in o.momento:
                continue
            salida.append(o)
        return salida

    def elegir(
        self,
        componente: str,
        comida: str,
        familia: str,
        usos: dict[str, int],
        tope_semana: int,
        rng: random.Random,
        excluir_reguladas: bool = False,
    ) -> Opcion | None:
        pool = self.candidatas(componente, comida, familia)
        # Si la ranura no pide una familia concreta, no puede tomar prestada una
        # familia que tiene cupo propio en el protocolo: se desbordaría su
        # frecuencia (el hígado 1x/semana acabaría apareciendo cuatro veces).
        if not familia or excluir_reguladas:
            pool = [o for o in pool if normalizar(o.familia) not in self.reguladas] or pool
        if not pool:
            return None

        disponibles = [
            o for o in pool if (not o.es_receta) or usos[o.id] < tope_semana
        ]
        if not disponibles:
            return None

        def puntaje(o: Opcion) -> tuple:
            clinico = -len(self.priorizar & set(o.aporta))   # menor = mejor
            return (usos[o.id], clinico, 0 if o.validada_en_cocina else 1, rng.random())

        return min(disponibles, key=puntaje)


# ---------------------------------------------------------------------------
# Construcción de una semana
# ---------------------------------------------------------------------------


def _ranuras(protocolo: dict, componente: str, comidas_validas: list[str]) -> list[tuple[int, str]]:
    """Todas las (dia, comida) donde este componente puede existir."""
    out = []
    for comida in protocolo["comidas"]:
        if comida["id"] not in comidas_validas:
            continue
        if componente not in comida["componentes"]:
            continue
        for d in range(7):
            out.append((d, comida["id"]))
    return out


def _reparto(reparto: dict, total: int) -> list[str]:
    """Convierte {avena:2, canihua:2, resto:...} en una lista de N familias."""
    fijas, resto_key = [], None
    for fam, n in reparto.items():
        if str(n).strip() == "resto":
            if resto_key:
                raise ErrorNutriOS("Una rotación no puede tener dos valores 'resto'.")
            resto_key = fam
        else:
            fijas += [fam] * int(n)
    if len(fijas) > total:
        raise ErrorNutriOS(
            f"Rotación imposible: pide {len(fijas)} apariciones para {total} ranuras."
        )
    faltan = total - len(fijas)
    if resto_key:
        fijas += [resto_key] * faltan
    elif faltan:
        fijas += [None] * faltan
    return fijas


def construir_semana(
    protocolo: dict, ficha: dict, rep: Repertorio, rng: random.Random, n_semana: int
) -> dict:
    porciones = ficha.get("porciones") or {}
    tope = int((protocolo.get("variedad") or {}).get("max_veces_misma_receta_semana", 99))
    usos: dict[str, int] = defaultdict(int)

    # semana[dia][comida][componente] = Opcion
    semana: dict = {d: {c["id"]: {} for c in protocolo["comidas"]} for d in range(7)}

    # --- componentes que NO se llenan siempre -------------------------------
    acopladas = protocolo.get("reglas_acopladas") or []
    dependientes = {r["entonces"].split(".")[-1] for r in acopladas}

    # --- 1. Reglas de frecuencia con familia (proteína, huevo, yogurt...) ---
    familia_forzada: dict[tuple[int, str, str], str] = {}
    limitados: dict[str, int] = {}

    for regla in protocolo.get("frecuencias_semanales") or []:
        comp = regla["componente"]
        comidas_validas = regla.get("en") or [c["id"] for c in protocolo["comidas"]]
        ranuras = _ranuras(protocolo, comp, comidas_validas)
        modo = regla.get("modo", "exacto")

        if regla.get("familia"):
            if modo == "relleno" or regla.get("cada_dias"):
                continue  # se resuelven después
            n = int(regla.get("minimo") or regla.get("veces") or 0)
            libres = [r for r in ranuras if (r[0], r[1], comp) not in familia_forzada]
            if n > len(libres):
                raise ErrorNutriOS(
                    f"Protocolo imposible: {comp}/{regla['familia']} pide {n} "
                    f"apariciones y solo hay {len(libres)} ranuras libres."
                )
            for d, c in rng.sample(libres, n):
                familia_forzada[(d, c, comp)] = regla["familia"]
        else:
            veces = regla.get("veces")
            if veces is not None and int(veces) < len(ranuras):
                limitados[comp] = (int(veces), comidas_validas)

    # --- 2. Rotaciones ------------------------------------------------------
    for rot in protocolo.get("rotaciones") or []:
        comp = rot["componente"]
        comidas_validas = rot.get("en") or [c["id"] for c in protocolo["comidas"]]
        ranuras = _ranuras(protocolo, comp, comidas_validas)
        ranuras = [r for r in ranuras if (r[0], r[1], comp) not in familia_forzada]
        familias = _reparto(rot["reparto"], len(ranuras))
        rng.shuffle(familias)
        for (d, c), fam in zip(ranuras, familias):
            if fam:
                familia_forzada[(d, c, comp)] = fam

    # --- 3. Ranuras a llenar -----------------------------------------------
    # Las reglas con 'veces' se reparten sobre TODAS las comidas de su ámbito,
    # no una vez por comida: 'menestra 3 veces en [almuerzo, cena]' son 3 en
    # total sobre las 14 ranuras de la semana, no 3 en cada una.
    a_llenar: list[tuple[int, str, str]] = []
    cubiertos: set[tuple[str, str]] = set()

    for comp, (veces, comidas_validas) in limitados.items():
        ranuras = _ranuras(protocolo, comp, comidas_validas)
        a_llenar += [(d, c, comp) for d, c in rng.sample(ranuras, veces)]
        cubiertos |= {(comp, c) for c in comidas_validas}

    for comida in protocolo["comidas"]:
        for comp in comida["componentes"]:
            if (comp, comida["id"]) in cubiertos or comp in dependientes:
                continue
            a_llenar += [(d, comida["id"], comp) for d in range(7)]

    # --- 4. Reglas acopladas ------------------------------------------------
    for regla in acopladas:
        disparador = regla["si"].split(".")[-1]
        objetivo = regla["entonces"].split(".")[-1]
        ambito = regla.get("ambito", "misma_comida")
        nuevas = []
        for d, c, comp in a_llenar:
            if comp != disparador:
                continue
            comida_obj = c if ambito == "misma_comida" else None
            candidatas_comida = (
                [comida_obj]
                if comida_obj
                else [m["id"] for m in protocolo["comidas"] if objetivo in m["componentes"]]
            )
            for cm in candidatas_comida:
                estructura = next((m for m in protocolo["comidas"] if m["id"] == cm), None)
                if estructura and objetivo in estructura["componentes"]:
                    if (d, cm, objetivo) not in a_llenar:
                        nuevas.append((d, cm, objetivo))
                    break
        a_llenar += nuevas

    # --- 5. Relleno de familias sobrantes -----------------------------------
    for regla in protocolo.get("frecuencias_semanales") or []:
        if regla.get("modo") != "relleno" or not regla.get("familia"):
            continue
        comp = regla["componente"]
        comidas_validas = regla.get("en") or [c["id"] for c in protocolo["comidas"]]
        for d, c in _ranuras(protocolo, comp, comidas_validas):
            familia_forzada.setdefault((d, c, comp), regla["familia"])

    # --- 5b. Comprobación de viabilidad -------------------------------------
    # Antes de elegir nada: ¿alcanza la biblioteca para llenar estas ranuras
    # sin romper el tope de repetición? Si no alcanza, reintentar es inútil.
    demanda: dict[tuple[str, str], int] = defaultdict(int)
    for d, c, comp in set(a_llenar):
        demanda[(comp, c)] += 1
    for (comp, c), n in demanda.items():
        opciones = rep.candidatas(comp, c)
        if any(not o.es_receta for o in opciones):
            continue  # los alimentos base no tienen tope de repetición
        techo = len(opciones) * tope
        if opciones and n > techo:
            raise ErrorNutriOS(
                f"Biblioteca insuficiente para «{comp}» en «{c}»: hacen falta {n} "
                f"apariciones por semana y solo hay {len(opciones)} opción(es) "
                f"disponible(s) para este paciente, con un tope de {tope} usos "
                f"por semana (máximo alcanzable: {techo}).\n"
                f"    Solución: añade al menos "
                f"{math.ceil(n / tope) - len(opciones)} receta(s) más de "
                f"componente '{comp}' con momento '{c}', o sube "
                f"'max_veces_misma_receta_semana' en el protocolo."
            )

    # --- 6. Elección concreta ----------------------------------------------
    sin_opcion: list[str] = []
    degradaciones: set[str] = set()
    orden = sorted(set(a_llenar), key=lambda t: (t[0], t[1], t[2]))
    for d, c, comp in orden:
        fam = familia_forzada.get((d, c, comp), "")
        elegida = rep.elegir(comp, c, fam, usos, tope, rng)
        if elegida is None and fam:
            # La familia que pedía el protocolo no tiene ninguna opción viable
            # para este paciente (alergia, rechazo o edad). Se degrada a otra,
            # pero NUNCA en silencio: queda registrado para el reporte de QA.
            degradaciones.add(
                f"{comp}/{fam}: sin opciones para este paciente; se sustituyó por otra familia"
            )
            elegida = rep.elegir(comp, c, "", usos, tope, rng, excluir_reguladas=True)
        if elegida is None:
            sin_opcion.append(f"{DIAS[d]} · {c} · {comp}" + (f" ({fam})" if fam else ""))
            continue
        usos[elegida.id] += 1
        semana[d][c][comp] = elegida

    if sin_opcion:
        raise ErrorNutriOS(
            "No hay opciones disponibles para estas ranuras (biblioteca insuficiente "
            "o filtros del paciente demasiado restrictivos):\n  - "
            + "\n  - ".join(sin_opcion[:12])
            + (f"\n  ... y {len(sin_opcion) - 12} más" if len(sin_opcion) > 12 else "")
        )

    # --- 7. Serialización ---------------------------------------------------
    salida = {"semana": n_semana, "dias": {}, "degradaciones": sorted(degradaciones)}
    for d in range(7):
        dia = {}
        for comida in protocolo["comidas"]:
            items = []
            for comp in comida["componentes"]:
                o = semana[d][comida["id"]].get(comp)
                if not o:
                    continue
                items.append(
                    {
                        "componente": comp,
                        "nombre": o.nombre,
                        "cantidad": porciones.get(comp, ""),
                        "receta_id": o.id if o.es_receta else None,
                    }
                )
            if items:
                dia[comida["id"]] = {
                    "nombre": comida["nombre"],
                    "hora": comida.get("hora", ""),
                    "items": items,
                }
        salida["dias"][DIAS[d]] = dia
    return salida


# ---------------------------------------------------------------------------
# Plan completo
# ---------------------------------------------------------------------------


def firma_dia(dia: dict) -> str:
    return "|".join(
        f"{c}:" + ",".join(i["nombre"] for i in v["items"]) for c, v in sorted(dia.items())
    )


def aplicar_reglas_periodicas(plan: dict, protocolo: dict, rep: Repertorio, rng: random.Random):
    """Reglas del tipo '1 vez cada 15 días', que exceden la semana."""
    dias_totales = len(plan["semanas"]) * 7
    for regla in protocolo.get("frecuencias_semanales") or []:
        if not regla.get("cada_dias"):
            continue
        comp, fam = regla["componente"], regla.get("familia", "")
        n = max(0, round(dias_totales / int(regla["cada_dias"]) * int(regla.get("veces", 1))))
        if n == 0:
            continue
        candidatas = rep.candidatas(comp, (regla.get("en") or [""])[0], fam)
        if not candidatas:
            continue
        ranuras = [
            (s["semana"], d, c)
            for s in plan["semanas"]
            for d, dia in s["dias"].items()
            for c, cm in dia.items()
            if c in (regla.get("en") or []) and any(i["componente"] == comp for i in cm["items"])
        ]
        if not ranuras:
            continue
        for sem, d, c in rng.sample(ranuras, min(n, len(ranuras))):
            elegida = rng.choice(candidatas)
            bloque = next(s for s in plan["semanas"] if s["semana"] == sem)
            for item in bloque["dias"][d][c]["items"]:
                if item["componente"] == comp:
                    item["nombre"] = elegida.nombre
                    item["receta_id"] = elegida.id if elegida.es_receta else None


def ensamblar(nombre_carpeta: str, semilla: int | None = None) -> dict:
    carpeta = DIR_PACIENTES / nombre_carpeta
    if not carpeta.exists():
        raise ErrorNutriOS(f"No existe la carpeta {carpeta}")

    ficha = cargar_ficha(carpeta)
    protocolo = cargar_protocolo(ficha["protocolo_sugerido"])
    recetas, avisos = cargar_biblioteca()
    rep = Repertorio(recetas + cargar_alimentos_base(), ficha, protocolo)

    variedad = protocolo.get("variedad") or {}
    n_semanas = int(ficha["semanas_plan"])
    base = semilla if semilla is not None else 0

    for intento in range(MAX_INTENTOS):
        rng = random.Random(base + intento)
        try:
            semanas = [
                construir_semana(protocolo, ficha, rep, rng, i + 1) for i in range(n_semanas)
            ]
        except ErrorNutriOS as e:
            if "Biblioteca insuficiente" in str(e) or intento >= 3:
                raise
            continue

        if variedad.get("no_repetir_dia_completo") and n_semanas > 1:
            firmas = [firma_dia(d) for s in semanas for d in s["dias"].values()]
            if len(firmas) != len(set(firmas)):
                continue
        break
    else:
        raise ErrorNutriOS(
            "No se logró un plan que cumpla las reglas de variedad. "
            "La biblioteca probablemente es demasiado pequeña para este paciente."
        )

    plan = {
        "paciente": ficha["paciente"],
        "edad_texto": ficha.get("edad_texto", f"{ficha['edad_meses']} meses"),
        "edad_meses": ficha["edad_meses"],
        "fecha": str(ficha.get("fecha", "")),
        "diagnostico_texto": ficha.get("diagnostico_texto", ""),
        "diagnosticos": ficha.get("diagnosticos") or [],
        "alergias": ficha.get("alergias") or [],
        "rechazos": ficha.get("rechazos") or [],
        "protocolo": protocolo["id"],
        "protocolo_nombre": protocolo["nombre"],
        "semanas": semanas,
        "marco_diario": protocolo.get("marco_diario") or {},
        "avisos_biblioteca": avisos,
        "degradaciones": sorted({d for s_ in semanas for d in s_["degradaciones"]}),
    }
    aplicar_reglas_periodicas(plan, protocolo, rep, random.Random(base))

    plan["recetas_usadas"] = sorted(
        {
            i["receta_id"]
            for s in plan["semanas"]
            for dia in s["dias"].values()
            for cm in dia.values()
            for i in cm["items"]
            if i["receta_id"]
        }
    )
    return plan


def main() -> int:
    ap = argparse.ArgumentParser(description="Ensambla el plan de un paciente.")
    ap.add_argument("paciente", help="nombre de la carpeta en /pacientes/")
    ap.add_argument("--semilla", type=int, default=None)
    args = ap.parse_args()

    try:
        plan = ensamblar(args.paciente, args.semilla)
    except ErrorNutriOS as e:
        print(f"\n✗ {e}\n", file=sys.stderr)
        return 1

    destino = DIR_PACIENTES / args.paciente / "plan.json"
    guardar_json(destino, plan)

    n_dias = len(plan["semanas"]) * 7
    print(f"✓ Plan ensamblado para {plan['paciente']}")
    print(f"  {len(plan['semanas'])} semana(s) · {n_dias} días · protocolo {plan['protocolo']}")
    print(f"  {len(plan['recetas_usadas'])} recetas del recetario")
    for a in plan["avisos_biblioteca"] + plan["degradaciones"]:
        print(f"  ⚠ {a}")
    print(f"  → {destino.relative_to(Path.cwd()) if destino.is_relative_to(Path.cwd()) else destino}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
