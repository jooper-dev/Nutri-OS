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

1. **Pasa todo a texto y hace inventario.** Antes de leer nada, convierte tus
   PDF y tus Word a texto y anota qué llegó: cuántos documentos, cuántas páginas,
   y **qué páginas son solo imagen y por tanto nadie ha leído**. Si adjuntaste dos
   veces el mismo archivo, te lo dice: casi siempre significa que falta otro.
2. **Lee el caso** y escribe una ficha con edad, diagnóstico, alergias,
   requerimiento calórico y porciones, **y de qué documento y página salió cada
   dato**. Te la muestra. Lo que buscó y no encontró también te lo dice, aparte y
   destacado, en vez de esconderlo en un párrafo.
3. **Comprueba si el caso necesita otra cosa antes que un plan** —una pérdida de
   peso que hay que estudiar, una alergia sospechada sin confirmar—. Si es así, se
   para y te lo explica.
4. **Revisa si faltan técnicas** para armar el plan y crea las que falten.
5. **Arma el plan**, y después **adapta cada receta a este niño en concreto**:
   su porción, su textura, sus ingredientes. Ese paso es nuevo y es el importante.
6. **Valida** y **saca los dos PDF**. Ahí se detiene para que los revises.

Si la validación encuentra un error de verdad —una alergia en el plato, un
alimento que ese niño rechaza, una cuenta que no cuadra—, **no genera nada** y te
dice qué pasó. No hay PDF malo que se te pueda escapar.

Hay una cosa que verás a veces en el informe y que **no es un error**: un
**hueco declarado**. Significa que en ese sitio del día no había ningún alimento
que cumpliera a la vez todo lo que este niño necesita, y el sistema prefirió
dejarlo escrito antes que rellenarlo con cualquier cosa. Te dice qué falta y qué
receta lo resolvería. Es información para el próximo control, no un fallo.

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

Lo primero que te va a poner delante es una sección corta: **«Léelo antes que
nada»**. Ahí va lo que no bloquea el plan y por eso mismo se pasa por alto:

**Exposiciones planificadas.** Cada ingrediente nuevo que el plan le mete a un
niño con selectividad sale nombrado, con su justificación, y **esperando tu visto
bueno**. Por ejemplo: *"zanahoria licuada, no está en su repertorio, entra porque
el color queda parejo y sin hebra visible"*. Si te parece pronto, dilo y esa
receta se rehace sin ella. Ningún alimento nuevo entra a escondidas.

**Estrategias de exposición encubierta.** Bajar el vaso de 300 a 250 ml sin
avisar, sumar gotas de jugo a la quinua semana a semana: eso lo propone el
sistema como propuesta y **lo decides tú**. Ya no se escribe dentro de una receta
que se pega en la refrigeradora, porque ahí es una instrucción a la madre para
modificar la comida del niño a escondidas, y esa es una decisión clínica tuya.

**Datos que faltan.** Si la hemoglobina o la ferritina no estaban en ningún
documento, te lo dice ahí y sale también en la portada del plan. Si crees que lo
tienes en otro sitio, pásalo y se rehace la ficha.

Después, dos cosas más:

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

**El sistema ya no inventa fotografías. Las pide.**

Cada receta del recetario ocupa dos páginas: una portada y las instrucciones. Si
hay una foto que corresponda a ese plato, la portada es la foto a página
completa, con el nombre encima. Si no la hay —que hoy es lo normal—, la portada
lleva el nombre del plato y tu nota en grande, y queda bien igual: no verás
huecos ni recuadros vacíos.

Al generar los PDF, el sistema te dice **qué platos no tienen foto y cómo se ven**
—«en bolitas, se ve la papa, un solo color»— y lo apunta en una lista. Esa lista
es la que usaríamos si algún día decides hacer una sesión de fotos: tú eliges qué
se retrata y cuándo.

**Por qué cambió.** Antes cada receta tenía su foto para siempre. Pero ahora cada
receta se adapta a cada niño, y si cambian los ingredientes cambia el aspecto: la
crema de quinua sola y la crema de quinua con manzana en trozos no se ven igual.
Enseñarle a una madre la foto de un plato que no es el suyo es peor que no
enseñarle ninguna. Ahora una foto solo se usa si el plato de esta receta se ve de
verdad como el de la foto.

Si algún día quieres una fotografía concreta, dilo y se prepara aparte.

Esto es aparte de los recetarios que vendes. Aquellos siguen pasando por tu
plantilla de Canva como siempre; esto es solo el anexo de cada paciente.

---

## La copia de seguridad · hazla

Esto es lo más aburrido de la guía y lo más importante que hay en ella.

**Los casos de tus pacientes viven solo en esta computadora.** No están en
GitHub, y no van a estarlo nunca: son historiales clínicos de menores y están
excluidos a propósito. Eso significa que si el disco se rompe, se pierden — y no
se pueden volver a pedir, porque la consulta ya pasó.

Conecta el disco externo, o abre la carpeta de tu nube, y dile a Claude:

> Haz la copia de seguridad en D:/Respaldos/NutriOS

Guarda un solo archivo `.zip` con fecha en el nombre, con todos los casos y la
tabla de consultas dentro, y te dice qué guardó y dónde.

Dos cosas que hace a propósito:

- **Si la ruta no existe, se niega y te lo dice.** No la crea él. Si tu disco
  externo no está conectado, crearla haría aparecer una carpeta vacía en la
  computadora, escribiría ahí el respaldo, y parecería que quedó guardado.
- **No deja guardarlo dentro del propio proyecto.** Una copia en el mismo disco
  no te protege de que se rompa ese disco.

Hazlo **después de cada día de consultas**. Es un minuto.

Ese `.zip` lleva datos clínicos de menores: guárdalo donde guardarías una
historia clínica en papel.

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
