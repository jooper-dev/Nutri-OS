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
    COMPONENTES_SIN_FILTRO_TEXTURA,
    DIR_PACIENTES,
    ErrorNutriOS,
    cargar_alimentos_base,
    cargar_biblioteca,
    cargar_ficha,
    cargar_protocolo,
    comprobar_rango_edad,
    coincide_rechazo,
    normalizar,
    resolver_regla_acoplada,
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

    estado_rango, mensaje_rango = comprobar_rango_edad(protocolo, ficha)
    if estado_rango == "fuera_sin_justificar":
        r.error(mensaje_rango)
    elif estado_rango == "fuera_justificado":
        r.aviso(mensaje_rango)

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

    # Una alergia que no coincide con ninguna etiqueta del catálogo no está
    # filtrando nada: el plan parece seguro y no lo es. Es el fallo más
    # peligroso posible del sistema, así que se detecta explícitamente.
    etiquetas_catalogo = {normalizar(a) for o in catalogo.values() for a in o.alergenos}
    for a in sorted(alergias):
        if a not in etiquetas_catalogo:
            r.error(
                f"La alergia «{a}» no corresponde a ninguna etiqueta de alérgeno del "
                f"catálogo, así que NO está excluyendo nada.\n"
                f"    Etiquetas reconocidas: {', '.join(sorted(etiquetas_catalogo)) or '(ninguna)'}.\n"
                f"    Añade esa etiqueta a los alimentos que la contengan en "
                f"datos/alimentos_base.yaml y al front-matter de las recetas afectadas, "
                f"o corrige el nombre en la ficha."
            )

    # Igual para los rechazos, pero como aviso: un rechazo mal escrito molesta,
    # no hace daño.
    for x in sorted(rechazos):
        if x and not any(coincide_rechazo(x, o) for o in catalogo.values()):
            r.aviso(
                f"El rechazo «{x}» no coincide con ningún alimento del catálogo: "
                f"no está excluyendo nada. Revisa cómo se escribe."
            )

    for sem, dia, cid, item in _items(plan):
        ident = item.get("receta_id") or normalizar(item["nombre"])
        opcion = catalogo.get(ident) or next(
            (o for o in catalogo.values() if o.nombre == item["nombre"]), None
        )
        donde = f"S{sem} · {dia} · {cid}"

        if opcion is None:
            r.error(f"{donde}: «{item['nombre']}» no existe en la biblioteca ni en alimentos base.")
            continue

        if opcion.nunca_recomendar:
            r.error(
                f"{donde}: «{item['nombre']}» está marcado 'nunca_recomendar' en el "
                f"catálogo y no puede aparecer en ningún plan.\n"
                f"    Es una decisión clínica de Paty, no un filtro por paciente: "
                f"si está aquí, el motor tiene un fallo."
            )

        choque = alergias & {normalizar(a) for a in opcion.alergenos}
        if choque:
            r.error(f"{donde}: «{item['nombre']}» contiene {', '.join(sorted(choque))} — ALERGIA declarada.")

        if any(coincide_rechazo(x, opcion) for x in rechazos):
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

    # --- 2b. Texturas -------------------------------------------------------
    # Una textura excluida en la ficha solo filtra a los alimentos que la
    # declaran. Los que no la declaran pasan sin que nadie los mire, y el plan
    # sale con sello de válido sin que la restricción se haya comprobado nunca.
    # Eso es un ERROR y detiene el pipeline, con el mismo criterio que una
    # alergia sin etiqueta en el catálogo: cuando el sistema no puede verificar
    # una restricción de seguridad, se para en vez de firmar.
    excluidas = {normalizar(t) for t in ficha.get("texturas_excluidas") or []}
    if excluidas:
        sin_declarar: set[str] = set()
        for sem, dia, cid, item in _items(plan):
            op = catalogo.get(item.get("receta_id") or "") or next(
                (o for o in catalogo.values() if o.nombre == item["nombre"]), None
            )
            if op is None:
                continue
            # Misma lista de exentos que usa el ensamblador. Si el validador no
            # la respetara, marcaría como error el agua y el aceite que el motor
            # acaba de poner a propósito, y los dos no pueden contradecirse.
            if op.componente in COMPONENTES_SIN_FILTRO_TEXTURA:
                continue
            if normalizar(op.textura) in excluidas:
                r.error(
                    f"S{sem} · {dia} · {cid}: «{item['nombre']}» es de textura "
                    f"{op.textura}, excluida para este paciente."
                )
            elif not op.textura:
                sin_declarar.add(item["nombre"])
        if sin_declarar:
            r.error(
                "La ficha excluye texturas ("
                + ", ".join(sorted(excluidas))
                + ") y estos alimentos del plan no declaran la suya, así que el "
                "filtro no los ha mirado y la restricción NO está comprobada: "
                + ", ".join(sorted(sin_declarar))
                + ".\n    Declara `textura` en el front-matter de esas recetas "
                "—python motor/migrar_textura.py— o en datos/alimentos_base.yaml. "
                "No se firma un plan cuya restricción de textura nadie ha podido "
                "verificar."
            )

    # --- 2c. Carga de seco en un paciente con riesgo de disfagia -----------
    # `texturas_excluidas` dice lo que el niño no se come; `riesgo_disfagia`
    # dice lo que le puede hacer daño al tragar. En aversión textural los dos
    # apuntan en direcciones opuestas: lo seco y lo crujiente es a la vez lo
    # único que acepta y el perfil de bolo que se impacta en un esófago
    # inflamado o estrecho.
    #
    # Esa tensión no la resuelve el motor, porque es criterio clínico. Pero sí
    # puede medirla y ponerla delante de Paty, en vez de dejarla enterrada en la
    # nota de una receta que quizá nadie abra. Por eso es AVISO y no ERROR: aquí
    # no hay una regla que se viole, hay una decisión que alguien tiene que
    # tomar mirando al paciente.
    if ficha.get("riesgo_disfagia"):
        SECAS = {"seca", "crujiente"}
        total = secas = 0
        solo_seco: list[str] = []
        for s in plan["semanas"]:
            for dia, comidas in s["dias"].items():
                for cid, comida in comidas.items():
                    txt = []
                    for item in comida["items"]:
                        op = catalogo.get(item.get("receta_id") or "") or next(
                            (o for o in catalogo.values() if o.nombre == item["nombre"]),
                            None,
                        )
                        # Las bebidas y los vehículos de grasa no forman bolo:
                        # se excluyen del recuento igual que del filtro.
                        if op is None or op.componente in COMPONENTES_SIN_FILTRO_TEXTURA:
                            continue
                        txt.append(normalizar(op.textura))
                    if not txt:
                        continue
                    total += len(txt)
                    secas += sum(1 for x in txt if x in SECAS)
                    if all(x in SECAS for x in txt):
                        solo_seco.append(f"S{s['semana']} · {dia} · {cid}")

        if solo_seco:
            extra = f" y {len(solo_seco) - 5} más" if len(solo_seco) > 5 else ""
            r.aviso(
                f"Riesgo de disfagia: {len(solo_seco)} comida(s) del plan no llevan "
                f"ningún elemento blando que ayude a bajar el bolo — "
                + "; ".join(solo_seco[:5])
                + extra
                + ". Conviene comprobar que cada una salga con bebida al lado y "
                "bocados pequeños."
            )
        if total and secas * 2 > total:
            r.aviso(
                f"Riesgo de disfagia: {secas} de {total} raciones del plan "
                f"({secas * 100 // total} %) son de textura seca o crujiente, que es "
                f"el perfil de bolo que se impacta. Si la ficha además excluye las "
                f"texturas húmedas, esta contradicción es clínica y no la resuelve "
                f"el motor: decide Paty, y a veces la respuesta es derivar."
            )

    # --- 3. Frecuencias del protocolo, recontadas ---------------------------
    for s in plan["semanas"]:
        n = s["semana"]
        conteo_comp: Counter = Counter()
        opciones_en: dict[tuple[str, str], list] = {}
        for dia, comidas in s["dias"].items():
            for cid, comida in comidas.items():
                for item in comida["items"]:
                    conteo_comp[(item["componente"], cid)] += 1
                    op = catalogo.get(item.get("receta_id") or "") or next(
                        (o for o in catalogo.values() if o.nombre == item["nombre"]), None
                    )
                    if op:
                        opciones_en.setdefault((item["componente"], cid), []).append(op)

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
                # Se cuenta con el mismo criterio de dos niveles que usa el
                # ensamblador (familia o id). Si aquí se contara solo por
                # familia, una regla escrita con un alimento concreto —
                # 'proteina/pavita'— daría siempre cero y bloquearía un plan
                # que en realidad la cumple.
                real = sum(
                    1
                    for c in ambito
                    for op in opciones_en.get((comp, c), [])
                    if op.responde_a(fam)
                )
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
        resuelta, problema = resolver_regla_acoplada(regla, protocolo)
        if not resuelta:
            r.error(
                f"Regla acoplada «{regla.get('si', '?')} -> "
                f"{regla.get('entonces', '?')}» no resoluble: {problema}."
            )
            continue
        disp = resuelta["disparador_componente"]
        familia_disp = resuelta["disparador_familia"]
        obj = resuelta["objetivo_componente"]
        ambito = resuelta["ambito"]

        def dispara(comida_id: str, comida: dict) -> bool:
            if comida_id not in resuelta["comidas_disparador"]:
                return False
            for item in comida["items"]:
                if item["componente"] != disp:
                    continue
                if not familia_disp:
                    return True
                ident = item.get("receta_id") or normalizar(item["nombre"])
                opcion = catalogo.get(ident) or next(
                    (o for o in catalogo.values() if o.nombre == item["nombre"]), None
                )
                if opcion and opcion.responde_a(familia_disp):
                    return True
            return False

        def tiene_objetivo(comida_id: str, comida: dict) -> bool:
            return comida_id in resuelta["comidas_objetivo"] and any(
                item["componente"] == obj for item in comida["items"]
            )

        for s in plan["semanas"]:
            for dia, comidas in s["dias"].items():
                if ambito == "misma_comida":
                    for cid, comida in comidas.items():
                        if dispara(cid, comida) and not tiene_objetivo(cid, comida):
                            r.error(
                                f"S{s['semana']} · {dia} · {cid}: hay {regla['si']} "
                                f"sin {regla['entonces']} "
                                f"({regla.get('razon', 'regla acoplada')})."
                            )
                else:
                    hay_disparador = any(dispara(cid, comida) for cid, comida in comidas.items())
                    hay_objetivo = any(
                        tiene_objetivo(cid, comida) for cid, comida in comidas.items()
                    )
                    if hay_disparador and not hay_objetivo:
                        r.error(
                            f"S{s['semana']} · {dia}: hay {regla['si']} sin "
                            f"{regla['entonces']} en todo el día "
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

    # --- 6b. Reglas del protocolo que el motor todavía no aplica ------------
    # Mejor decirlo que dejar creer que se cumplieron.
    # Solo lo que ensamblar.py aplica de verdad: ampliar esta lista sin implementar
    # la funcionalidad apaga el aviso que protege la revisión clínica.
    IMPLEMENTADAS = {"priorizar_aporta"}
    for dx in ficha.get("diagnosticos") or []:
        ajuste = (protocolo.get("preferencias_clinicas") or {}).get(dx) or {}
        for clave in ajuste:
            if clave not in IMPLEMENTADAS and clave != "nota_qa":
                r.aviso(
                    f"El protocolo declara «{clave}» para {dx}, pero el motor todavía "
                    f"no lo aplica: queda a criterio de Paty."
                )
        if ajuste.get("nota_qa"):
            r.aviso(f"Nota del protocolo ({dx}): {ajuste['nota_qa']}")

    for clave in ("introduccion_progresiva", "progresion_textura", "exclusiones_duras"):
        if protocolo.get(clave):
            r.aviso(
                f"El protocolo declara «{clave}», que el motor aún no hace cumplir. "
                f"Revísalo a mano."
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
