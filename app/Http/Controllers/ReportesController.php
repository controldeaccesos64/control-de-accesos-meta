<?php

namespace App\Http\Controllers;

use App\Models\Acceso;
use App\Models\Cargo;
use App\Models\Secretaria;
use App\Models\Gerencia;
use App\Models\Mantenimiento;
use App\Models\Material;
use App\Models\Piso;
use App\Models\Puerta;
use App\Models\Role;
use App\Models\TipoPuerta;
use App\Models\Ups;
use App\Models\UpsBitacora;
use App\Models\User;
use Illuminate\Database\Eloquent\Builder;
use Illuminate\Http\Request;
use Illuminate\Support\Facades\Log;
use Inertia\Inertia;
use Inertia\Response;
use Symfony\Component\HttpFoundation\StreamedResponse;
use Throwable;

class ReportesController extends Controller
{
    /**
     * Mostrar página de reportes
     */
    public function index(Request $request): Response
    {
        if (!$request->user()->hasPermission('view_reportes')) {
            abort(403, 'No tienes permiso para ver reportes.');
        }

        // Obtener datos para los filtros
        $roles = Role::query()
            ->whereIn('name', ['visitante', 'servidor_publico', 'proveedor', 'funcionario'])
            ->orderBy('name')
            ->get(['id', 'name']);
        $cargos = Cargo::query()->orderBy('name')->get(['id', 'name']);
        $secretarias = Secretaria::query()
            ->where('activo', true)
            ->with('piso')
            ->orderBy('nombre')
            ->get(['id', 'nombre', 'piso_id']);

        $gerencias = Gerencia::query()
            ->where('activo', true)
            ->with('secretaria')
            ->orderBy('nombre')
            ->get(['id', 'nombre', 'secretaria_id']);
        $pisos = Piso::query()
            ->where('activo', true)
            ->orderBy('orden')
            ->get(['id', 'nombre']);
        $puertas = Puerta::query()
            ->where('activo', true)
            ->orderBy('nombre')
            ->get(['id', 'nombre']);
        $tiposPuerta = TipoPuerta::query()
            ->where('activo', true)
            ->orderBy('nombre')
            ->get(['id', 'nombre']);
        $materiales = Material::query()
            ->where('activo', true)
            ->orderBy('nombre')
            ->get(['id', 'nombre']);

        $puedeExportarUpsMonitoreo = $request->user()->hasPermission('view_ups');
        $upsList = $puedeExportarUpsMonitoreo
            ? Ups::query()
                ->where('activo', true)
                ->orderBy('nombre')
                ->get(['id', 'nombre', 'codigo'])
            : collect();

        return Inertia::render('Reportes/Index', [
            'roles' => $roles,
            'cargos' => $cargos,
            'secretarias' => $secretarias,
            'gerencias' => $gerencias,
            'pisos' => $pisos,
            'puertas' => $puertas,
            'tiposPuerta' => $tiposPuerta,
            'materiales' => $materiales,
            'puedeExportarUpsMonitoreo' => $puedeExportarUpsMonitoreo,
            'upsList' => $upsList,
        ]);
    }

    /**
     * Exportar monitoreo / bitácora operativa de UPS (CSV).
     */
    public function exportarUpsMonitoreo(Request $request): StreamedResponse
    {
        if (!$request->user()->hasPermission('view_reportes') || !$request->user()->hasPermission('view_ups')) {
            abort(403, 'No tienes permiso para exportar monitoreo de UPS.');
        }

        $validated = $request->validate([
            'fecha_desde' => ['nullable', 'date'],
            'fecha_hasta' => ['nullable', 'date'],
            'ups_id' => ['nullable', 'integer', 'exists:ups,id'],
        ]);

        $query = UpsBitacora::query()->with(['ups', 'creadoPor']);

        if (!empty($validated['fecha_desde'])) {
            $query->whereDate('created_at', '>=', $validated['fecha_desde']);
        }
        if (!empty($validated['fecha_hasta'])) {
            $query->whereDate('created_at', '<=', $validated['fecha_hasta']);
        }
        if (!empty($validated['ups_id'])) {
            $query->where('ups_id', $validated['ups_id']);
        }

        $registros = $query->orderBy('created_at')->orderBy('id')->get();

        $filename = 'reporte_ups_monitoreo_' . date('Y-m-d_His') . '.csv';

        return response()->streamDownload(function () use ($registros) {
            $file = fopen('php://output', 'w');
            fprintf($file, chr(0xEF) . chr(0xBB) . chr(0xBF));

            fputcsv($file, [
                'ID Bitácora',
                'UPS ID',
                'UPS Nombre',
                'UPS Código',
                'Fecha registro',
                'Ind. Normal',
                'Ind. Batería',
                'Ind. Bypass',
                'Ind. Falla',
                'Voltaje entrada (V)',
                'Frecuencia entrada (Hz)',
                'Voltaje salida (V)',
                'Frecuencia salida (Hz)',
                'Potencia salida (W)',
                'Voltaje batería (V)',
                '% Batería',
                'Tiempo respaldo (min)',
                'Tiempo descarga (min)',
                'Estado batería',
                'Temperatura (°C)',
                'Modelo/marca (IA)',
                'Alarmas (IA)',
                'Fase A V',
                'Fase A A',
                'Fase A Hz',
                'Fase B V',
                'Fase B A',
                'Fase B Hz',
                'Fase C V',
                'Fase C A',
                'Fase C Hz',
                'Otros valores IA (plano)',
                'Observaciones',
                'Datos extraídos (JSON completo)',
                'Creado por',
                'Email creador',
            ]);

            foreach ($registros as $r) {
                $extra = is_array($r->datos_extraidos) ? $r->datos_extraidos : [];
                $extraStr = $extra === [] ? '' : json_encode($extra, JSON_UNESCAPED_UNICODE);

                fputcsv($file, [
                    $r->id,
                    $r->ups_id,
                    $r->ups?->nombre ?? '',
                    $r->ups?->codigo ?? '',
                    $r->created_at?->format('Y-m-d H:i:s') ?? '',
                    $r->indicador_normal ? 'Sí' : 'No',
                    $r->indicador_battery ? 'Sí' : 'No',
                    $r->indicador_bypass ? 'Sí' : 'No',
                    $r->indicador_fault ? 'Sí' : 'No',
                    $r->input_voltage,
                    $r->input_frequency,
                    $r->output_voltage,
                    $r->output_frequency,
                    $r->output_power,
                    $r->battery_voltage,
                    $r->battery_percentage,
                    $r->battery_tiempo_respaldo,
                    $r->battery_tiempo_descarga,
                    $r->battery_estado ?? '',
                    $r->temperatura,
                    $extra['modelo_ups'] ?? '',
                    self::upsAlarmasPlano($extra),
                    self::upsFaseValor($extra, 'a', 'voltage'),
                    self::upsFaseValor($extra, 'a', 'corriente'),
                    self::upsFaseValor($extra, 'a', 'frecuencia'),
                    self::upsFaseValor($extra, 'b', 'voltage'),
                    self::upsFaseValor($extra, 'b', 'corriente'),
                    self::upsFaseValor($extra, 'b', 'frecuencia'),
                    self::upsFaseValor($extra, 'c', 'voltage'),
                    self::upsFaseValor($extra, 'c', 'corriente'),
                    self::upsFaseValor($extra, 'c', 'frecuencia'),
                    self::upsDatosAdicionalesPlano($extra),
                    $r->observaciones ?? '',
                    $extraStr,
                    $r->creadoPor?->name ?? '',
                    $r->creadoPor?->email ?? '',
                ]);
            }

            fclose($file);
        }, $filename, [
            'Content-Type' => 'text/csv; charset=UTF-8',
            'Content-Disposition' => 'attachment; filename="' . $filename . '"',
        ]);
    }

    /**
     * Exportar reporte de usuarios
     */
    public function exportarUsuarios(Request $request): StreamedResponse
    {
        if (!$request->user()->hasPermission('view_reportes') || !$request->user()->hasPermission('view_users')) {
            abort(403, 'No tienes permiso para exportar reportes de usuarios.');
        }

        $filtros = $request->only([
            'role_id',
            'cargo_id',
            'gerencia_id',
            'activo',
        ]);

        $query = User::query()
            ->with(['role', 'cargo', 'gerencia.secretaria.piso']);

        if (!empty($filtros['role_id'])) {
            $query->where('role_id', $filtros['role_id']);
        }

        if (!empty($filtros['cargo_id'])) {
            $query->where('cargo_id', $filtros['cargo_id']);
        }

        if (!empty($filtros['gerencia_id'])) {
            $query->where('gerencia_id', $filtros['gerencia_id']);
        }

        if (isset($filtros['activo']) && $filtros['activo'] !== '') {
            $query->where('activo', (bool) $filtros['activo']);
        }

        $usuarios = $query->orderBy('name')->get();

        $filename = 'reporte_usuarios_' . date('Y-m-d_His') . '.csv';

        return response()->streamDownload(function () use ($usuarios) {
            $file = fopen('php://output', 'w');

            // BOM para UTF-8 (Excel compatibility)
            fprintf($file, chr(0xEF) . chr(0xBB) . chr(0xBF));

            // Encabezados
            fputcsv($file, [
                'ID',
                'Nombre',
                'Email',
                'Tipo de vinculación',
                'Rol (permisos)',
                'Cargo (registro)',
                'Secretaría',
                'Gerencia',
                'Activo',
                'Fecha Expiración',
            ]);

            // Datos
            foreach ($usuarios as $usuario) {
                fputcsv($file, [
                    $usuario->id,
                    $usuario->name,
                    $usuario->email,
                    $usuario->role?->name ?? '',
                    $usuario->cargo?->name ?? '',
                    $usuario->cargo_texto ?? '',
                    $usuario->gerencia?->secretaria?->nombre ?? '',
                    $usuario->gerencia?->nombre ?? '',
                    $usuario->activo ? 'Sí' : 'No',
                    $usuario->fecha_expiracion?->format('Y-m-d') ?? '',
                ]);
            }

            fclose($file);
        }, $filename, [
            'Content-Type' => 'text/csv; charset=UTF-8',
            'Content-Disposition' => 'attachment; filename="' . $filename . '"',
        ]);
    }

    /**
     * Mostrar reporte de accesos con filtros
     */
    public function accesos(Request $request): Response
    {
        if (!$request->user()->hasPermission('view_reportes')) {
            abort(403, 'No tienes permiso para ver reportes.');
        }

        $request->validate([
            'fecha_desde' => ['nullable', 'date'],
            'fecha_hasta' => ['nullable', 'date'],
        ]);

        $perPage = (int) ($request->query('per_page', 20));
        $perPage = max(1, min(100, $perPage));

        $filtros = $request->only([
            'fecha_desde',
            'fecha_hasta',
            'secretaria_id',
            'gerencia_id',
            'piso_id',
            'tipo_evento',
            'permitido',
        ]);

        $query = Acceso::query()
            ->with(['user.role', 'user.gerencia.secretaria', 'puerta.piso']);

        self::applyAccesosReportFilters($query, $filtros);

        $accesos = $query->orderByDesc('fecha_acceso')->paginate($perPage)->withQueryString()
            ->through(fn(Acceso $a) => [
                'id' => $a->id,
                'fecha_acceso' => self::formatFechaAccesoParaReporte($a),
                'user' => $a->user ? [
                    'id' => $a->user->id,
                    'name' => $a->user->name,
                    'email' => $a->user->email,
                ] : null,
                'puerta' => $a->puerta ? [
                    'id' => $a->puerta->id,
                    'nombre' => $a->puerta->nombre,
                    'piso' => $a->puerta->piso ? [
                        'id' => $a->puerta->piso->id,
                        'nombre' => $a->puerta->piso->nombre,
                    ] : null,
                ] : null,
                'tipo_evento' => $a->tipo_evento,
                'permitido' => (bool) $a->permitido,
                'motivo_denegacion' => $a->motivo_denegacion,
            ]);

        // Datos para filtros
        $secretarias = Secretaria::query()
            ->where('activo', true)
            ->orderBy('nombre')
            ->get(['id', 'nombre']);

        $gerencias = Gerencia::query()
            ->where('activo', true)
            ->with('secretaria')
            ->orderBy('nombre')
            ->get(['id', 'nombre', 'secretaria_id']);

        $pisos = Piso::query()
            ->where('activo', true)
            ->orderBy('orden')
            ->get(['id', 'nombre']);

        return Inertia::render('Reportes/Accesos', [
            'accesos' => $accesos,
            'secretarias' => $secretarias,
            'gerencias' => $gerencias,
            'pisos' => $pisos,
            'filters' => $filtros,
        ]);
    }

    /**
     * Exportar reporte de accesos
     */
    public function exportarAccesos(Request $request): StreamedResponse
    {
        if (!$request->user()->hasPermission('view_reportes')) {
            abort(403, 'No tienes permiso para exportar reportes.');
        }

        $request->validate([
            'fecha_desde' => ['nullable', 'date'],
            'fecha_hasta' => ['nullable', 'date'],
        ]);

        $filtros = $request->only([
            'fecha_desde',
            'fecha_hasta',
            'secretaria_id',
            'gerencia_id',
            'piso_id',
            'tipo_evento',
            'permitido',
        ]);

        $filename = 'reporte_accesos_' . date('Y-m-d_His') . '.csv';

        return response()->streamDownload(static function () use ($filtros) {
            $handle = fopen('php://output', 'w');
            if ($handle === false) {
                return;
            }

            $query = Acceso::query()
                ->with(['user.gerencia.secretaria', 'puerta.piso']);

            self::applyAccesosReportFilters($query, $filtros);

            fprintf($handle, chr(0xEF) . chr(0xBB) . chr(0xBF));

            fputcsv($handle, [
                'ID',
                'Fecha y Hora',
                'Usuario',
                'Email Usuario',
                'Piso',
                'Puerta',
                'Tipo Evento',
                'Permitido',
                'Motivo Denegación',
                'Observaciones',
            ]);

            // Sin ->get() masivo: paginar por lotes manteniendo el mismo criterio de orden que el visor.
            $query->orderByDesc('fecha_acceso')->orderByDesc('id');

            foreach ($query->lazy(750) as $acceso) {
                fputcsv($handle, [
                    $acceso->id,
                    self::formatFechaAccesoParaCsv($acceso),
                    self::csvTextField($acceso->user?->name ?? 'N/A'),
                    self::csvTextField($acceso->user?->email ?? 'N/A'),
                    self::csvTextField($acceso->puerta?->piso?->nombre ?? 'N/A'),
                    self::csvTextField($acceso->puerta?->nombre ?? 'N/A'),
                    self::csvTextField($acceso->tipo_evento ?? ''),
                    $acceso->permitido ? 'Sí' : 'No',
                    self::csvTextField($acceso->motivo_denegacion ?? ''),
                    self::csvTextField($acceso->observaciones ?? ''),
                ]);
            }

            fclose($handle);
        }, $filename, [
            'Content-Type' => 'text/csv; charset=UTF-8',
            'Content-Disposition' => 'attachment; filename="' . $filename . '"',
        ]);
    }

    /**
     * Filtros compartidos entre la vista paginada y la exportación CSV.
     *
     * @param  Builder<Acceso>  $query
     */
    private static function applyAccesosReportFilters(Builder $query, array $filtros): void
    {
        if (! empty($filtros['fecha_desde'])) {
            $query->whereDate('fecha_acceso', '>=', $filtros['fecha_desde']);
        }

        if (! empty($filtros['fecha_hasta'])) {
            $query->whereDate('fecha_acceso', '<=', $filtros['fecha_hasta']);
        }

        if (! empty($filtros['gerencia_id'])) {
            if ($filtros['gerencia_id'] === 'despacho') {
                $query->whereHas('user', function ($q) {
                    $q->whereNull('gerencia_id');
                });
            } else {
                $query->whereHas('user', function ($q) use ($filtros) {
                    $q->where('gerencia_id', $filtros['gerencia_id']);
                });
            }
        } elseif (! empty($filtros['secretaria_id'])) {
            $query->whereHas('user.gerencia', function ($q) use ($filtros) {
                $q->where('secretaria_id', $filtros['secretaria_id']);
            });
        }

        if (! empty($filtros['piso_id'])) {
            $query->whereHas('puerta', function ($q) use ($filtros) {
                $q->where('piso_id', $filtros['piso_id']);
            });
        }

        if (! empty($filtros['tipo_evento'])) {
            $query->where('tipo_evento', $filtros['tipo_evento']);
        }

        $permitido = self::parsePermitidoQueryValue($filtros['permitido'] ?? null);
        if ($permitido !== null) {
            $query->where('permitido', $permitido);
        }
    }

    /**
     * Interpreta permitido desde query string (GET): evita (bool) "false" === true.
     */
    private static function parsePermitidoQueryValue(mixed $value): ?bool
    {
        if ($value === null || $value === '') {
            return null;
        }

        if (is_bool($value)) {
            return $value;
        }

        return filter_var($value, FILTER_VALIDATE_BOOLEAN, FILTER_NULL_ON_FAILURE);
    }

    /**
     * Texto seguro para celdas CSV (saltos de línea; UTF-8 inválido).
     */
    private static function csvTextField(mixed $value): string
    {
        if ($value === null) {
            return '';
        }

        $s = is_string($value) ? $value : (string) $value;
        $s = str_replace(["\r\n", "\r", "\n"], ' ', $s);

        if ($s !== '' && function_exists('mb_check_encoding') && ! mb_check_encoding($s, 'UTF-8')) {
            $converted = @mb_convert_encoding($s, 'UTF-8', 'UTF-8');

            return $converted !== false ? $converted : '';
        }

        return $s;
    }

    /**
     * Exportar reporte de mantenimientos
     */
    public function exportarMantenimientos(Request $request): StreamedResponse
    {
        if (!$request->user()->hasPermission('view_reportes') || !$request->user()->hasPermission('view_mantenimientos')) {
            abort(403, 'No tienes permiso para exportar reportes de mantenimientos.');
        }

        $filtros = $request->only([
            'fecha_desde',
            'fecha_hasta',
            'puerta_id',
            'tipo',
        ]);

        $query = Mantenimiento::query()
            ->with(['puerta', 'creadoPor']);

        if (!empty($filtros['fecha_desde'])) {
            $query->whereDate('fecha_mantenimiento', '>=', $filtros['fecha_desde']);
        }

        if (!empty($filtros['fecha_hasta'])) {
            $query->whereDate('fecha_mantenimiento', '<=', $filtros['fecha_hasta']);
        }

        if (!empty($filtros['puerta_id'])) {
            $query->where('puerta_id', $filtros['puerta_id']);
        }

        if (!empty($filtros['tipo'])) {
            $query->where('tipo', $filtros['tipo']);
        }

        $mantenimientos = $query->orderByDesc('fecha_mantenimiento')->get();

        $filename = 'reporte_mantenimientos_' . date('Y-m-d_His') . '.csv';

        return response()->streamDownload(function () use ($mantenimientos) {
            $file = fopen('php://output', 'w');

            // BOM para UTF-8
            fprintf($file, chr(0xEF) . chr(0xBB) . chr(0xBF));

            // Encabezados
            fputcsv($file, [
                'ID',
                'Fecha Mantenimiento',
                'Puerta',
                'Usuario',
                'Tipo',
                'Fecha Fin Programada',
                'Otros Defectos',
                'Observaciones',
            ]);

            // Datos
            foreach ($mantenimientos as $mantenimiento) {
                fputcsv($file, [
                    $mantenimiento->id,
                    $mantenimiento->fecha_mantenimiento?->format('Y-m-d') ?? '',
                    $mantenimiento->puerta?->nombre ?? 'N/A',
                    $mantenimiento->creadoPor?->name ?? 'N/A',
                    $mantenimiento->tipo ?? '',
                    $mantenimiento->fecha_fin_programada?->format('Y-m-d') ?? '',
                    $mantenimiento->otros_defectos ?? '',
                    $mantenimiento->observaciones ?? '',
                ]);
            }

            fclose($file);
        }, $filename, [
            'Content-Type' => 'text/csv; charset=UTF-8',
            'Content-Disposition' => 'attachment; filename="' . $filename . '"',
        ]);
    }

    /**
     * Exportar reporte de puertas
     */
    public function exportarPuertas(Request $request): StreamedResponse
    {
        if (!$request->user()->hasPermission('view_reportes') || !$request->user()->hasPermission('view_puertas')) {
            abort(403, 'No tienes permiso para exportar reportes de puertas.');
        }

        $filtros = $request->only([
            'piso_id',
            'tipo_puerta_id',
            'material_id',
            'activo',
        ]);

        $query = Puerta::query()
            ->with(['piso', 'tipoPuerta', 'material']);

        if (!empty($filtros['piso_id'])) {
            $query->where('piso_id', $filtros['piso_id']);
        }

        if (!empty($filtros['tipo_puerta_id'])) {
            $query->where('tipo_puerta_id', $filtros['tipo_puerta_id']);
        }

        if (!empty($filtros['material_id'])) {
            $query->where('material_id', $filtros['material_id']);
        }

        if (isset($filtros['activo']) && $filtros['activo'] !== '') {
            $query->where('activo', (bool) $filtros['activo']);
        }

        $puertas = $query->orderBy('nombre')->get();

        $filename = 'reporte_puertas_' . date('Y-m-d_His') . '.csv';

        return response()->streamDownload(function () use ($puertas) {
            $file = fopen('php://output', 'w');

            // BOM para UTF-8
            fprintf($file, chr(0xEF) . chr(0xBB) . chr(0xBF));

            // Encabezados
            fputcsv($file, [
                'ID',
                'Nombre',
                'Piso',
                'Tipo',
                'Material',
                'IP Entrada',
                'IP Salida',
                'Tiempo Apertura (seg)',
                'Alto (cm)',
                'Largo (cm)',
                'Ancho (cm)',
                'Peso (kg)',
                'Activo',
            ]);

            // Datos
            foreach ($puertas as $puerta) {
                fputcsv($file, [
                    $puerta->id,
                    $puerta->nombre ?? '',
                    $puerta->piso?->nombre ?? '',
                    $puerta->tipoPuerta?->nombre ?? '',
                    $puerta->material?->nombre ?? '',
                    $puerta->ip_entrada ?? '',
                    $puerta->ip_salida ?? '',
                    $puerta->tiempo_apertura ?? '',
                    $puerta->alto ?? '',
                    $puerta->largo ?? '',
                    $puerta->ancho ?? '',
                    $puerta->peso ?? '',
                    $puerta->activo ? 'Sí' : 'No',
                ]);
            }

            fclose($file);
        }, $filename, [
            'Content-Type' => 'text/csv; charset=UTF-8',
            'Content-Disposition' => 'attachment; filename="' . $filename . '"',
        ]);
    }

    /**
     * @param  array<string, mixed>  $datosExtraidos
     */
    private static function upsFaseValor(array $datosExtraidos, string $fase, string $campo): string
    {
        $v = data_get($datosExtraidos, "fases.{$fase}.{$campo}");
        if ($v === null || $v === '') {
            return '';
        }

        return is_scalar($v) ? (string) $v : '';
    }

    /**
     * @param  array<string, mixed>  $datosExtraidos
     */
    private static function upsAlarmasPlano(array $datosExtraidos): string
    {
        $a = $datosExtraidos['alarmas'] ?? null;
        if (! is_array($a) || $a === []) {
            return '';
        }

        return implode(' | ', array_map(static function ($x) {
            return str_replace(["\r", "\n"], ' ', (string) $x);
        }, $a));
    }

    /**
     * Formatea fecha_acceso para la tabla del reporte (evita 500 si hay fechas corruptas o inválidas en BD).
     */
    private static function formatFechaAccesoParaReporte(Acceso $acceso): ?string
    {
        try {
            return $acceso->fecha_acceso?->format('d/m/Y H:i:s');
        } catch (Throwable $e) {
            Log::warning('Reporte accesos: fecha_acceso no parseable', [
                'acceso_id' => $acceso->id,
                'raw' => $acceso->getRawOriginal('fecha_acceso'),
                'message' => $e->getMessage(),
            ]);

            $raw = $acceso->getRawOriginal('fecha_acceso');
            if (is_string($raw) && $raw !== '' && $raw !== '0000-00-00 00:00:00') {
                return $raw;
            }

            return null;
        }
    }

    /**
     * Formatea fecha_acceso para CSV (misma tolerancia que la vista web).
     */
    private static function formatFechaAccesoParaCsv(Acceso $acceso): string
    {
        try {
            return $acceso->fecha_acceso?->format('Y-m-d H:i:s') ?? '';
        } catch (Throwable $e) {
            Log::warning('Export accesos CSV: fecha_acceso no parseable', [
                'acceso_id' => $acceso->id,
                'raw' => $acceso->getRawOriginal('fecha_acceso'),
                'message' => $e->getMessage(),
            ]);
            $raw = $acceso->getRawOriginal('fecha_acceso');

            return is_string($raw) && $raw !== '' && $raw !== '0000-00-00 00:00:00' ? $raw : '';
        }
    }

    private static function upsDatosAdicionalesPlano(array $datosExtraidos): string
    {
        $d = $datosExtraidos['datos_adicionales'] ?? null;
        if (! is_array($d) || $d === []) {
            return '';
        }
        ksort($d);
        $parts = [];
        foreach ($d as $k => $v) {
            if (is_array($v) || is_object($v)) {
                $v = json_encode($v, JSON_UNESCAPED_UNICODE);
            }
            $parts[] = $k.'='.str_replace(["\r", "\n"], ' ', (string) $v);
        }

        return implode('; ', $parts);
    }
}
