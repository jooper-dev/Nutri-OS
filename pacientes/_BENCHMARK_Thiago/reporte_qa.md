# Reporte de validación — Thiago R. M.

Protocolo: Escolar 6–11 años · dieta de eliminación de 4 alimentos  ·  2 semana(s)  ·  fecha 2026-08-11

## Resultado

**BLOQUEADO** — 1 error(es). El plan no debe renderizarse.

## Errores

- La ficha excluye texturas (humeda, liquida, mixta) y estos alimentos del plan no declaran la suya, así que el filtro no los ha mirado y la restricción NO está comprobada: Bastones de yuca dorada, Compota de pera, Crema de quinua, Mazamorra de kiwicha, Paletas de mango, Tacacho de bellaco.
    Declara `textura` en el front-matter de esas recetas —python motor/migrar_textura.py— o en datos/alimentos_base.yaml. No se firma un plan cuya restricción de textura nadie ha podido verificar.

## Avisos

- 6 receta(s) del plan no están marcadas como probadas en cocina: bastones-yuca-dorada, compota-pera-avena, crema-quinua-manzana, mazamorra-kiwicha, paletas-mango-papaya, tacacho-platano-bellaco
- El protocolo declara «max_recetas_nuevas_semana» para selectividad, pero el motor todavía no lo aplica: queda a criterio de Paty.
- Nota del protocolo (selectividad): priorizar recetas ya aceptadas por el paciente
- Nota del protocolo (bajo_peso): Plan de recuperación ponderal. Verificar densidad calórica por bocado, no volumen de la ración: el paciente come poco y lento. Controlar peso cada 2 semanas y avisar si no hay ganancia al mes.

- Sustitución forzada: carbohidrato/quinua: sin opciones para este paciente; se sustituyó por otra familia
- Sustitución forzada: cereal/avena: sin opciones para este paciente; se sustituyó por otra familia
- Sustitución forzada: cereal/canihua: sin opciones para este paciente; se sustituyó por otra familia
- Sustitución forzada: cereal/harinas: sin opciones para este paciente; se sustituyó por otra familia

---

Este reporte lo genera código, no un modelo de lenguaje: los conteos son aritmética sobre el plan ya construido. Un error aquí siempre es real.

Revisión final y firma clínica: Nut. Patricia López.