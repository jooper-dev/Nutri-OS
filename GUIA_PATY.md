# Guía de uso — para Paty

Esta guía es lo único que necesitas leer. No hace falta entender el código.

---

## Cómo se abre

En **Claude Cowork**, abre el proyecto `Nutri-OS`. Con eso basta: Claude ya sabe
cómo funciona todo el sistema.

No hay que escribir comandos, ni pegar prompts, ni crear carpetas, ni tocar
archivos. Le hablas normal y le arrastras lo que tengas.

---

## Paso 1 · Arrastra y pide

Abre el chat, **arrastra los archivos de la consulta** y escribe lo que quieres.
Así de literal:

> Hazme un plan de dos semanas para este paciente.

No tienes que crear ninguna carpeta, ni ordenar nada, ni ponerle nombre a los
archivos. De eso se encarga el sistema solo: guarda el material donde
corresponde y empieza a leer el caso.

Arrastra **todo lo que tengas, tal como esté**:

- fotos o PDF del laboratorio
- la historia clínica o tus notas
- peso, talla y fecha de nacimiento
- capturas de WhatsApp con lo que la mamá contó
- audios de la consulta, si los grabas

**Y cuenta en el mensaje lo que sepas de la consulta.** Lo que escribes se guarda
con el caso igual que un documento: *"la mamá dice que no come nada verde"*,
*"son dos semanas"*, *"la familia acaba de mudarse de la selva"*. Eso es
información clínica y cuenta como tal.

Lo único que puede preguntarte al principio es **cómo se llama el niño**, y solo
si no lo encuentra en lo que le pasaste. Nada más.

**Lo que sí es obligatorio que esté en algún sitio:** fecha de nacimiento (o edad
exacta), peso, talla y las alergias. Si falta algo de eso, el sistema se detiene
y te lo dice en vez de inventarlo.

Si es un control de un niño que ya pasó por aquí, arrastra lo nuevo y dilo: se
añade a su caso, no se empieza otro.

---

## Paso 2 · Lo que hace solo

Después de tu mensaje, y sin preguntarte nada más:

1. **Lee el caso** y escribe una ficha con edad, diagnóstico, alergias,
   requerimiento calórico y porciones. Te la muestra.
2. **Revisa si faltan recetas** para armar el plan.
3. **Crea las que falten**, con la auditoría de seguridad pediátrica de siempre.
4. **Arma el plan** y lo valida.
5. **Genera las fotos** de las recetas que aún no tengan.
6. **Genera los dos PDF** y se detiene para que los revises.

Si la validación encuentra un error de verdad —una alergia en el plato, una
cuenta que no cuadra—, **no genera nada** y te dice qué pasó. No hay PDF malo que
se te pueda escapar.

---

## Paso 3 · Los PDF

Salen dos PDF, y Claude te dice en el chat dónde quedaron. No tienes que ir a
buscarlos: si no los encuentras, pídeselos y te los pone delante.

- **`Plan_Mateo.pdf`** — el horario semanal, apaisado, para imprimir y pegar en
  la refrigeradora. Una hoja por semana.
- **`Recetario_Mateo.pdf`** — solo las recetas que aparecen en ese plan, con
  ingredientes, preparación y conservación.

Hay un caso en que sale **un solo PDF**: cuando el plan no lleva ninguna receta
porque todo lo que come ese niño son preparaciones simples que no necesitan
instrucciones —un puré de camote, una fruta picada—. Hoy es lo que pasa con los
planes de 6 meses. Claude te lo dice cuando ocurre; no es un fallo.

Si una semana te queda con la letra muy apretada, pídele:

> Genera el plan en dos caras.

Sale entonces a dos hojas por semana (lunes a jueves y viernes a domingo), con la
letra más grande.

---

## Paso 4 · Tu revisión

Aquí decides tú, sobre el documento terminado — el mismo que va a recibir la
familia, no un informe técnico. Claude te resume en el chat lo que conviene
mirar, y tú lo contrastas con el PDF delante.

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
lo que corresponda, vuelve a armar el plan y te genera los PDF otra vez. Las veces
que haga falta: regenerarlos no cuesta nada.

Cuando estén como los quieres, **los PDF los subes tú a Drive y compartes el
enlace**, como haces siempre. Ese es el momento en que el plan sale de tu mano, y
por eso la última palabra es tuya: el sistema nunca entrega nada a nadie.

---

## Las fotos de las recetas

Las recetas del recetario llevan fotografía, y **no tienes que pedirla**. Al
generar los PDF, el sistema mira qué recetas del plan no tienen foto todavía y
las consigue en ese momento. Es parte de hacer el recetario, no un paso aparte.

La imagen queda guardada junto a la receta **para siempre**. La siguiente
paciente que lleve esa misma receta la recibe con foto sin volver a generar nada,
así que cada plan tarda menos que el anterior.

Si por lo que sea una foto no se puede generar —se cayó el servicio, se acabó la
cuota—, **el recetario sale igual**: esa receta lleva una banda del color que le
toca en vez de la fotografía, y te lo dice en una línea. Nunca vas a quedarte sin
plan por una foto.

Si una foto no te convence, dilo y se rehace solo esa.

Para que se generen hace falta una clave de la API de Google. Danny la configura
una vez en la computadora y ya no se vuelve a tocar. **Nunca la escribas en un
archivo ni la pegues en el chat**: si eso pasa, hay que cambiarla.

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

Se genera **`salidas/metricas.html`**: lo abres con doble clic y se ve en el
navegador como una página normal. Trae consultas del mes, facturado, ticket
promedio, la evolución mes a mes, el desglose por tipo de consulta, los motivos
más frecuentes y el detalle de cada paciente.

No hay que instalar nada ni entrar a ningún sitio: es un archivo en tu
computadora. Puedes guardarlo o imprimirlo si te sirve.

Si regeneras el plan de una paciente, no se duplica el ingreso: la fila se
reemplaza sola.

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
final son tuyas. Se detiene siempre después de generar los PDF y antes de que
salgan de tu computadora: nada llega a una familia sin que tú lo hayas mirado.

---

## Si algo falla

Dile a Claude que ejecute el chequeo del sistema. Revisa dependencias, protocolos,
biblioteca y fichas, y te dice exactamente qué está mal:

> Corre el chequeo del sistema.

Los mensajes de error están escritos para leerse enteros: dicen qué falta y qué
hacer. Si uno no se entiende, pásaselo a Danny tal cual.
