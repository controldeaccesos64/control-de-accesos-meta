# Manual de Usuario - Sistema de Control de Accesos

## Objetivo del sistema
Este sistema permite administrar usuarios, puertas, permisos de acceso, credenciales (QR y NFC), equipos UPS, dependencias y reportes de operación. Tambien incluye un protocolo de emergencia para apertura masiva de puertas.

## Alcance de este manual
- Documento en formato Markdown (`.md`), 100% textual.
- Organizado por modulos (cada seccion del menu lateral).
- Enfocado en operacion funcional y uso diario.

## Perfiles de uso
- **Administrador:** Gestion integral de modulos, configuracion y seguridad.
- **Operador:** Uso operativo de ingresos, consultas y seguimiento.
- **Visitante:** Acceso limitado a `Ingreso` y `Soporte` segun permisos.

## Convenciones de navegacion
- El menu lateral muestra modulos segun permisos del usuario.
- Si una accion no aparece, normalmente se debe a falta de permiso.
- Los listados incluyen busqueda, filtros y paginacion cuando aplica.
- En formularios, los mensajes en rojo indican validaciones pendientes.

## Indice por modulos
1. [Dashboard](#modulo-dashboard)
2. [Usuarios](#modulo-usuarios)
3. [Puertas](#modulo-puertas)
4. [Roles / Permisos](#modulo-roles--permisos)
5. [Ingreso](#modulo-ingreso)
6. [Tarjetas NFC](#modulo-tarjetas-nfc)
7. [UPS](#modulo-ups)
8. [Dependencias](#modulo-dependencias)
9. [Reportes](#modulo-reportes)
10. [Protocolo](#modulo-protocolo)
11. [Soporte](#modulo-soporte)

---

## Plantilla de lectura por modulo
Cada modulo de este manual mantiene la misma estructura:
1. Proposito del modulo
2. Cuando usarlo
3. Pasos basicos de operacion
4. Campos/opciones principales
5. Resultados esperados
6. Errores frecuentes y solucion rapida

---

## Modulo: Dashboard

### Proposito del modulo
Ofrecer una vista rapida del estado general del sistema: usuarios, accesos, puertas y mantenimientos.

### Cuando usarlo
- Al iniciar sesion para revisar estado operativo.
- Antes de generar reportes o ejecutar acciones administrativas.

### Pasos basicos de operacion
1. Ingresar al modulo `Dashboard`.
2. Revisar tarjetas de indicadores principales.
3. Verificar graficas de comportamiento reciente (accesos, mantenimientos).
4. Detectar anomalías o faltantes de informacion.

### Campos/opciones principales
- Totales de usuarios (activos/inactivos).
- Ingresos unicos del dia.
- Conteo de puertas activas.
- Graficas de accesos por hora/dia y estado de mantenimientos.

### Resultados esperados
- Comprension general del estado del sistema en pocos segundos.
- Identificacion temprana de tendencias o incidentes.

### Errores frecuentes y solucion rapida
- **No aparecen datos:** validar que existan registros en el periodo.
- **Acceso denegado al modulo:** solicitar permiso `view_dashboard`.

---

## Modulo: Usuarios

### Proposito del modulo
Administrar ciclo de vida de usuarios: creacion, consulta, actualizacion y seguimiento de estado.

### Cuando usarlo
- Alta de nuevos usuarios.
- Consulta de informacion personal, tipo de vinculacion y estado.
- Revision de usuarios activos/inactivos.

### Pasos basicos de operacion
1. Entrar en `Usuarios`.
2. Usar buscador por nombre, correo, identidad o caso.
3. Crear con `Nuevo` o consultar con `Ver`.
4. Completar/actualizar datos y guardar.

### Campos/opciones principales
- Nombre, email y numero de identidad.
- Tipo de vinculacion (visitante, servidor publico, proveedor).
- Rol/Cargo asignado.
- Secretaria/Gerencia.
- Estado activo.

### Resultados esperados
- Usuarios correctamente registrados y localizables.
- Control de vigencia y estado de habilitacion.

### Errores frecuentes y solucion rapida
- **Email duplicado:** usar un correo unico.
- **Usuario no visible en listado:** limpiar filtros y revisar paginacion.
- **Sin boton de creacion:** validar permisos `view_users` y `create_users`.

---

## Modulo: Puertas

### Proposito del modulo
Gestionar puertas fisicas, conectividad, estado operativo y configuraciones de acceso.

### Cuando usarlo
- Alta o ajuste de una puerta.
- Revision de conectividad de entrada/salida.
- Verificacion por piso y estado de mantenimiento.

### Pasos basicos de operacion
1. Abrir `Puertas`.
2. Filtrar por piso o revisar todas.
3. Validar estado visual de conexion (entrada/salida).
4. Crear o editar segun necesidad.
5. Usar `Refrescar Conexiones` para validar estado actual.

### Campos/opciones principales
- Nombre de puerta, piso, tipo de puerta.
- IP de entrada y salida.
- Estado activa/inactiva.
- Indicadores de mantenimiento.
- Opciones de accesibilidad y restricciones especiales.

### Resultados esperados
- Inventario de puertas actualizado.
- Estado de red y operacion visible para toma de decisiones.

### Errores frecuentes y solucion rapida
- **Conexion en rojo:** verificar red, IP y energia del controlador.
- **Puerta no aparece:** revisar filtros por piso.
- **Cambios no aplicados:** confirmar guardado y refrescar vista.

---

## Modulo: Roles / Permisos

### Proposito del modulo
Definir que puede hacer cada perfil de usuario y que accesos operativos tendra.

### Cuando usarlo
- Crear un nuevo rol.
- Ajustar permisos de un rol existente.
- Revisar impacto de un rol sobre usuarios asignados.

### Pasos basicos de operacion
1. Ingresar a `Roles / Permisos`.
2. Buscar rol por nombre o descripcion.
3. Crear o abrir `Gestionar Permisos`.
4. Asignar permisos y guardar cambios.
5. Verificar comportamiento con un usuario de prueba.

### Campos/opciones principales
- Nombre y descripcion del rol.
- Estado activo/inactivo.
- Requiere permiso superior (si aplica).
- Conteo de usuarios asociados.

### Resultados esperados
- Roles claros, reutilizables y consistentes con politicas internas.
- Usuarios con acceso alineado a sus funciones.

### Errores frecuentes y solucion rapida
- **Usuario no ve un modulo:** revisar permisos del rol.
- **Accion bloqueada pese a ver el modulo:** falta permiso especifico de accion.
- **Eliminacion de rol riesgosa:** validar usuarios asociados antes de eliminar.

---

## Modulo: Ingreso

### Proposito del modulo
Generar y administrar codigos QR de acceso para usuarios habilitados y visitantes.

### Cuando usarlo
- Emision de QR personal o para terceros autorizados.
- Gestion de vigencia de acceso.
- Consulta de QR activo y datos de expiracion.

### Pasos basicos de operacion
1. Entrar en `Ingreso`.
2. Seleccionar usuario (si el perfil lo permite).
3. Definir datos de vigencia (especialmente para visitantes).
4. Generar QR.
5. Validar token y fecha de expiracion mostrados por el sistema.

### Campos/opciones principales
- Usuario objetivo.
- Rango de fechas (inicio/fin cuando aplique).
- Estado de QR personal.
- Token y fecha de expiracion.

### Resultados esperados
- QR valido emitido con vigencia correcta.
- Registro claro de fecha de generacion y expiracion.

### Errores frecuentes y solucion rapida
- **No genera QR:** verificar usuario activo y permisos del operador.
- **Vigencia incorrecta:** revisar fechas y zona horaria del sistema.
- **Visitante sin QR visible:** crear uno nuevo o verificar expiracion.

---

## Modulo: Tarjetas NFC

### Proposito del modulo
Administrar tarjetas NFC y su asignacion a usuarios para control de acceso.

### Cuando usarlo
- Registro de nueva tarjeta.
- Consulta de asignacion por usuario.
- Baja o depuracion de tarjetas.

### Pasos basicos de operacion
1. Acceder a `Tarjetas NFC`.
2. Buscar por codigo, nombre, usuario o cedula.
3. Crear con `Nueva Tarjeta` o abrir detalle con `Ver`.
4. Asignar/validar usuario y vigencia.
5. Eliminar tarjeta solo si ya no aplica.

### Campos/opciones principales
- Codigo de tarjeta.
- Nombre o alias.
- Usuario asignado.
- Gerencia asociada.
- Fecha de expiracion.
- Estado activa/inactiva.

### Resultados esperados
- Tarjetas correctamente trazables y asociadas.
- Menor riesgo de uso no autorizado.

### Errores frecuentes y solucion rapida
- **Tarjeta no encontrada:** validar codigo exacto y filtros.
- **Tarjeta sin asignar:** completar asociacion a usuario.
- **No permite eliminar:** confirmar permisos de eliminacion.

---

## Modulo: UPS

### Proposito del modulo
Llevar inventario y seguimiento operativo de UPS, incluyendo filtros y mantenimiento.

### Cuando usarlo
- Alta y consulta de equipos UPS.
- Revision por piso y busqueda tecnica.
- Seguimiento de estado activo/inactivo.

### Pasos basicos de operacion
1. Abrir `UPS`.
2. Aplicar filtros por piso o texto.
3. Consultar tarjetas de equipos y su estado.
4. Entrar a `Ver` o `Editar` segun permisos.

### Campos/opciones principales
- Codigo y nombre de UPS.
- Marca/modelo/serial (segun registro).
- Piso asociado.
- Estado activo/inactivo.
- Evidencia fotografica (si existe en el registro).

### Resultados esperados
- Inventario actualizado y facil de auditar.
- Acceso rapido al detalle tecnico de cada equipo.

### Errores frecuentes y solucion rapida
- **Listado vacio:** revisar filtros activos.
- **No aparece opcion editar:** verificar permiso `edit_ups`.
- **Datos incompletos:** actualizar ficha tecnica del equipo.

---

## Modulo: Dependencias

### Proposito del modulo
Gestionar estructura organizacional (secretarias y gerencias) utilizada en usuarios y reportes.

### Cuando usarlo
- Alta de una secretaria.
- Revision de gerencias por dependencia.
- Mantenimiento de estado organizacional activo/inactivo.

### Pasos basicos de operacion
1. Ir a `Dependencias`.
2. Buscar por nombre de secretaria o piso.
3. Crear secretaria o abrir detalle con `Ver`.
4. Editar informacion y confirmar cambios.
5. Eliminar solo cuando no afecte procesos activos.

### Campos/opciones principales
- Nombre de secretaria.
- Piso asociado.
- Conteo de gerencias.
- Estado activo/inactivo.

### Resultados esperados
- Estructura organizacional consistente para todo el sistema.
- Mejor calidad de filtros en usuarios y reportes.

### Errores frecuentes y solucion rapida
- **No encuentra una secretaria:** limpiar buscador y validar escritura.
- **Error al eliminar:** revisar relaciones activas (usuarios/gerencias).
- **Sin boton de alta:** validar permisos del perfil.

---

## Modulo: Reportes

### Proposito del modulo
Generar reportes parametrizados y exportaciones CSV para analisis operativo.

### Cuando usarlo
- Exportar usuarios filtrados.
- Exportar accesos por fechas y ubicacion.
- Consultar reportes de mantenimiento y actividad.

### Pasos basicos de operacion
1. Entrar a `Reportes`.
2. Seleccionar el tipo de reporte (usuarios, accesos, mantenimientos, etc.).
3. Configurar filtros requeridos.
4. Ejecutar `Exportar` o abrir vista de reporte de accesos.
5. Validar archivo generado.

### Campos/opciones principales
- Fechas desde/hasta.
- Dependencia (secretaria) y gerencia.
- Piso.
- Tipo de evento (entrada/salida/denegado).
- Estado permitido/denegado.
- Tipo de vinculacion y rol.

### Resultados esperados
- Archivos CSV utiles para auditoria y gestion.
- Trazabilidad de eventos segun filtros seleccionados.

### Errores frecuentes y solucion rapida
- **Exportacion vacia:** ampliar rango de fechas o quitar filtros.
- **Gerencia deshabilitada:** seleccionar primero secretaria.
- **Formato inesperado:** abrir CSV en herramienta compatible con UTF-8.

---

## Modulo: Protocolo

### Proposito del modulo
Activar apertura de emergencia para todas las puertas disponibles por un tiempo controlado.

### Cuando usarlo
- Solo en contingencias reales y autorizadas.
- Cuando se requiere evacuacion o apertura inmediata general.

### Pasos basicos de operacion
1. Abrir `Protocolo`.
2. Revisar advertencias y cantidad de puertas que se abriran.
3. Definir duracion en segundos (segun procedimiento interno).
4. Confirmar activacion del protocolo.
5. Monitorear corridas recientes y tiempo restante.

### Campos/opciones principales
- Duracion de apertura en segundos.
- Lista de puertas incluidas en la corrida.
- Historial de corridas (usuario y fecha/hora).

### Resultados esperados
- Activacion registrada de forma auditable.
- Apertura temporal coordinada conforme al tiempo definido.

### Errores frecuentes y solucion rapida
- **No hay puertas disponibles:** revisar conectividad y estado activo.
- **Boton deshabilitado:** validar permisos o condiciones de red.
- **Duracion no permitida:** usar valores dentro del rango aceptado.

---

## Modulo: Soporte

### Proposito del modulo
Brindar ayuda operativa con preguntas frecuentes del sistema.

### Cuando usarlo
- Dudas funcionales sobre registro de usuarios.
- Configuracion de permisos o mantenimiento.
- Orientacion rapida para procesos comunes.

### Pasos basicos de operacion
1. Ir a `Soporte`.
2. Abrir la pregunta frecuente relacionada.
3. Seguir los pasos indicados.
4. Si persiste el problema, escalar al administrador del sistema.

### Campos/opciones principales
- Acordeones de FAQ por tema.
- Contenido guiado de procedimientos frecuentes.
- Recomendaciones de seguridad y buenas practicas.

### Resultados esperados
- Resolucion rapida de dudas comunes.
- Reduccion de errores operativos repetitivos.

### Errores frecuentes y solucion rapida
- **No ves ciertos FAQ:** algunas respuestas dependen de permisos.
- **Instruccion no aplica a tu perfil:** validar rol con administracion.

---

## Orden recomendado de lectura/implementacion del manual
Para entrenamiento o despliegue documental, se sugiere este orden:
1. `Ingreso`
2. `Puertas`
3. `Usuarios`
4. `Roles / Permisos`
5. `Dependencias`
6. `Tarjetas NFC`
7. `UPS`
8. `Dashboard`
9. `Reportes`
10. `Protocolo`
11. `Soporte`

## Preguntas frecuentes generales
### Como saber si un modulo requiere permiso?
Si el modulo no aparece en el menu o no muestra botones de accion, el perfil no tiene permiso suficiente.

### Que hago si no puedo guardar un formulario?
Revisar validaciones marcadas en rojo, campos obligatorios y formato de fechas.

### Como evitar errores por filtros?
Antes de concluir que no hay datos, usar `Limpiar` en filtros y repetir la consulta.

## Glosario minimo
- **Modulo:** Seccion funcional del menu lateral.
- **Rol/Cargo:** Conjunto de permisos asignado a un usuario.
- **Permiso:** Regla que habilita ver/crear/editar/eliminar acciones.
- **QR:** Credencial digital de acceso.
- **NFC:** Credencial fisica por proximidad.
- **Corrida de emergencia:** Ejecucion temporal del protocolo de apertura masiva.

## Checklist de calidad del manual
- [x] Documento unico en formato `.md`.
- [x] Contenido sin imagenes.
- [x] Una seccion por cada modulo del menu.
- [x] Estructura uniforme por modulo.
- [x] Lenguaje operativo y accionable.
