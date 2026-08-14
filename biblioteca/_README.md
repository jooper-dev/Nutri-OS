# Biblioteca de bases

Aquí no hay recetas terminadas. Hay **bases**: una técnica, un esqueleto de
ingredientes y sus reglas de seguridad. Una base por archivo `.md`, con
front-matter YAML y `tipo: base`. El nombre del archivo coincide con el `id`.

**Una base no se imprime nunca.** Lo que llega al recetario de una familia es la
base ya resuelta contra ese niño concreto, y eso vive en
`pacientes/<paciente>/recetas/`.

## Por qué

Porque Paty nunca sirve una receta tal cual: adapta porción, textura,
ingredientes y presentación a cada niño. El sistema hacía lo contrario —si un
requerimiento del paciente coincidía con una receta guardada, la metía— y así
fue como a un paciente cuya anamnesis dice, con esas palabras, «no pan, ni pan
con palta», le salió el pan con palta en el plan. Y una crema de quinua con
manzana a un niño que pide la quinua sola.

Ninguna de esas dos recetas era mala. Lo que faltaba era el paso de adaptarlas.

## Qué se acumula

Las **técnicas**, no los platos. «Lenteja colada sin cáscara» sirve para
cualquier niño que rechace la fibra; «hamburguesitas de lenteja de Haziel, 6
piezas de 3,5 cm» no le sirve a nadie más. Por eso la biblioteca guarda lo
primero y la carpeta del paciente guarda lo segundo.

Cuando un plan necesita una base que no está aquí, se escribe con
`prompts/P1_RECETAS.md`. La siguiente paciente que la necesite ya la tiene.

## Campos que lee el código

- `tipo: base` — obligatorio. Sin él la base se omite, para que una receta
  terminada no pueda colarse en la biblioteca y volver a servirse sin adaptar.
- `componente` y `momento` — deciden en qué ranura del plan puede entrar.
- `edad_min_meses` y `alergenos_posibles` — el filtro de seguridad.
- `familia` — las reglas de frecuencia del protocolo (pescado 2x, huevo 3–4x).
- `aporta` — la priorización clínica (anemia → hierro, estreñimiento → fibra).

Si estos campos están mal, el plan sale mal aunque la técnica sea perfecta.

### `alergenos_posibles` no es `alergenos_presentes`

Es lo que la técnica **puede** traer según cómo se instancie. Una base de
milanesa declara `[gluten, huevo]` aunque exista una versión sin ninguno de los
dos: el filtro descarta la base entera para un alérgico, que es el lado correcto
por el que equivocarse. La receta del paciente declara después lo que lleva **de
verdad**, y eso el validador lo comprueba contra su lista de ingredientes.

## `validada_en_cocina`

Toda base nace en `false`. **Solo Paty lo cambia a `true`, y solo después de
haberla preparado.** El validador avisa cuando un plan usa bases sin probar; el
ensamblador prefiere las probadas cuando puede elegir.

## Las bases que vienen en este repositorio

Son **semillas**: se escribieron para poner el motor en marcha y probarlo de
punta a punta. Todas están marcadas `origen: creada` y `validada_en_cocina:
false`. Revísalas o reemplázalas antes de usarlas con una paciente real.
