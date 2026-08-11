# Guía de uso — para Paty

Esta guía es lo único que necesitas leer. No hace falta entender el código.

---

## Cómo se abre

En **Claude Cowork**, abre la carpeta `Nutri-OS`. Con eso basta: Claude lee solo
el archivo `CLAUDE.md` y ya sabe cómo funciona todo el sistema.

No hay que escribir comandos ni pegar prompts. Le hablas normal.

---

## Paso 1 · Prepara la carpeta de la paciente

Dentro de `pacientes/`, crea una carpeta con el nombre del niño, y dentro otra
llamada `fuente`:

```
pacientes/
  Mateo/
    fuente/
```

En `fuente/` metes **todo lo que tengas de la consulta, tal como esté**:

- fotos o PDF del laboratorio
- la historia clínica o tus notas
- peso, talla y fecha de nacimiento
- capturas de WhatsApp con lo que la mamá contó
- audios de la consulta, si los grabas

No hace falta ordenarlo ni transcribirlo. El sistema lo lee y lo organiza.

**Lo único que sí es obligatorio:** fecha de nacimiento (o edad exacta), peso,
talla y las alergias. Si falta algo de eso, el sistema se detiene y te lo dice
en vez de inventarlo.

---

## Paso 2 · Pídelo

En el chat de Cowork escribes algo así:

> Prepara el plan de Mateo. Son 2 semanas.

Claude hace, en este orden:

1. **Lee el caso** y escribe una ficha con edad, diagnóstico, alergias,
   requerimiento calórico y porciones. Te la muestra.
2. **Revisa si faltan recetas** para armar el plan.
3. **Crea las que falten**, con la auditoría de seguridad pediátrica de siempre.
4. **Arma el plan** y lo valida.
5. **Se detiene y te pregunta.**

---

## Paso 3 · Tu revisión

Aquí es donde el sistema te entrega el `reporte_qa.md` y espera. Míralo con calma:
es el momento en que decides tú, no la máquina.

Presta atención sobre todo a dos cosas:

**Sustituciones forzadas.** Cuando tu protocolo pedía algo que este niño no puede
comer, el sistema lo cambió. Por ejemplo: *"proteina/pescado: sin opciones para
este paciente"* significa que tu protocolo pide pescado dos veces por semana pero
este niño lo rechaza, así que esas dos comidas llevan otra cosa. Tú decides si te
parece bien o si prefieres reforzar de otra manera.

**Recetas sin probar en cocina.** Las recetas nuevas se marcan así hasta que las
preparas. Cuando ya la hayas hecho y funcione, dile a Claude:

> Marca la receta de muffins de zanahoria como validada en cocina.

A partir de ahí el sistema la prefiere sobre las que no has probado.

Si algo no te cuadra, dilo con tus palabras: *"cámbiame las menestras del martes"*,
*"este niño no come camote"*, *"prefiero avena en vez de cañihua"*. Claude ajusta
lo que corresponda y vuelve a armar el plan.

---

## Paso 4 · Los PDF

Cuando das el visto bueno, salen dos archivos en la carpeta de la paciente:

- **`Plan_Mateo.pdf`** — el horario semanal, apaisado, para imprimir y pegar en
  la refrigeradora. Una hoja por semana.
- **`Recetario_Mateo.pdf`** — solo las recetas que aparecen en ese plan, con
  ingredientes, preparación y conservación.

Si una semana te queda con la letra muy apretada, pídele:

> Genera el plan en dos caras.

Sale entonces a dos hojas por semana (lunes a jueves y viernes a domingo), con la
letra más grande.

Los PDF los subes tú a Drive y compartes el enlace, como haces siempre.

---

## Las fotos de las recetas

Las recetas del recetario pueden llevar fotografía. Funciona así:

Cuando se crea una receta nueva, el sistema decide qué tipo de encuadre le
corresponde y prepara el texto para el generador de imágenes. Tú solo dices:

> Genera las fotos que falten para el plan de Mateo.

La imagen queda guardada junto a la receta **para siempre**. La siguiente
paciente que lleve esa misma receta la recibe con foto sin volver a generar nada.

Si una foto no te convence, dilo y se rehace solo esa. Y si prefieres no usar
fotos en un plan concreto, el recetario sale igual de bien: en lugar de la
fotografía va una banda del color de la receta.

Esto es aparte de los recetarios que vendes. Aquellos siguen pasando por tu
plantilla de Canva como siempre; esto es solo el anexo de cada paciente.

---

## Paso 5 · El registro

Al final puedes decirle:

> Registra la consulta de Mateo, cobré 189 soles.

Se guarda en una tabla local con fecha, paciente, edad, tipo de consulta,
protocolo, motivo e importe. Todo eso sale del plan solo: **lo único que tienes
que decir es cuánto cobraste.**

Y cuando quieras ver cómo va el mes:

> Muéstrame las métricas del mes.

Te da consultas, facturado, ticket promedio, desglose por tipo de consulta y los
motivos de consulta más frecuentes. Si regeneras el plan de una paciente, no se
duplica el ingreso: la fila se reemplaza.

---

## Cosas que conviene saber

**La biblioteca crece sola.** Cada receta que se crea queda guardada. La próxima
paciente que necesite algo parecido ya lo tiene, sin volver a generarlo. Al cabo
de unos meses, la mayoría de los planes salen de recetas que tú ya validaste.

**Ningún plan es copia de otro.** El sistema filtra por edad, alergias, rechazos y
diagnóstico de cada niño, y las combinaciones cambian en cada plan. Lo que se
reutiliza son las recetas, no el plan.

**Nada de las pacientes sale de la computadora.** La carpeta `pacientes/` está
excluida del repositorio. Los PDF se generan en local, sin enviar nada a ningún
servicio.

**El sistema no firma nada.** Prepara y ordena; la revisión clínica y la decisión
final son tuyas. Por eso se detiene siempre antes de generar los PDF.

---

## Si algo falla

Dile a Claude que ejecute el chequeo del sistema. Revisa dependencias, protocolos,
biblioteca y fichas, y te dice exactamente qué está mal:

> Corre el chequeo del sistema.

Los mensajes de error están escritos para leerse enteros: dicen qué falta y qué
hacer. Si uno no se entiende, pásaselo a Danny tal cual.
