# Biblioteca de recetas

Una receta por archivo `.md`, con front-matter YAML generado por
`prompts/P1_RECETAS.md`. El nombre del archivo debe coincidir con el campo `id`.

## Cómo crece

No hay que digitalizar nada por adelantado. Cuando un plan necesita una receta
que no está aquí, se genera con P1 y se guarda. La siguiente paciente que la
necesite ya la tiene gratis. A los pocos meses, la mayoría de los planes salen
de recetas ya existentes.

## Campos que lee el código

- `componente` y `momento` — deciden en qué ranura del plan puede entrar.
- `edad_min_meses` y `alergenos_presentes` — el filtro de seguridad.
- `familia` — las reglas de frecuencia del protocolo (pescado 2x, huevo 3–4x).
- `aporta` — la priorización clínica (anemia → hierro, estreñimiento → fibra).

Si estos campos están mal, el plan sale mal aunque la receta sea perfecta.

## `validada_en_cocina`

Toda receta nace en `false`. **Solo Paty lo cambia a `true`, y solo después de
haberla preparado.** El validador avisa cuando un plan lleva recetas sin probar;
el ensamblador prefiere las probadas cuando puede elegir.

## Las recetas que vienen en este repositorio

Las 11 recetas iniciales son **semillas**: se crearon para poner el motor en
marcha y probarlo de punta a punta. Están marcadas `origen: creada` y
`validada_en_cocina: false`. Revísalas o reemplázalas antes de usarlas con una
paciente real.
