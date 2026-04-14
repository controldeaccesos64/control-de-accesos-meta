<template>
    <div
        class="min-h-screen bg-gradient-to-br from-[#008c3a] via-[#006a2d] to-[#008c3a] flex items-center justify-center px-4 py-4"
    >
        <div class="max-w-md w-full">
            <!-- Header con Logo y Textos -->
            <div class="text-center mb-5">
                <!-- Logo Gobernación del Meta con contenedor elegante -->
                <div class="mb-4 flex justify-center">
                    <div class="bg-white/10 backdrop-blur-sm rounded-xl p-3 shadow-xl border border-white/20">
                        <img
                            src="/images/logo-gobernacion-meta.png"
                            alt="Gobernación del Meta"
                            class="h-20 w-auto object-contain drop-shadow-lg"
                            onerror="this.style.display='none'"
                        />
                    </div>
                </div>

                <!-- Título principal -->
                <h1 class="text-3xl font-bold text-white mb-2 tracking-tight">
                    Gobernación del Meta
                </h1>

                <!-- Separador decorativo -->
                <div class="flex items-center justify-center mb-2">
                    <div class="h-px w-12 bg-white/30"></div>
                    <div class="mx-2 w-1.5 h-1.5 rounded-full bg-white/40"></div>
                    <div class="h-px w-12 bg-white/30"></div>
                </div>

                <!-- Subtítulo del sistema -->
                <p class="text-white/95 text-lg font-medium mb-1">
                    Sistema de Control de Accesos
                </p>

                <!-- Frase institucional -->
                <p class="text-white/85 italic text-sm font-light">
                    Por un futuro para todos los colombianos
                </p>
            </div>

            <!-- Card -->
            <div
                class="bg-white/98 backdrop-blur-sm border border-white/30 rounded-xl p-6 shadow-2xl"
            >
                <!-- Título del formulario con separador -->
                <div class="mb-5">
                    <h2 class="text-xl font-semibold text-[#008c3a] mb-2 text-center">
                        Iniciar Sesión
                    </h2>
                    <div class="h-0.5 w-16 bg-gradient-to-r from-transparent via-[#008c3a] to-transparent mx-auto rounded-full"></div>
                </div>

                <form @submit.prevent="submit">
                    <!-- Email -->
                    <div class="mb-3">
                        <label
                            for="email"
                            class="block text-sm font-medium text-gray-700 mb-1.5"
                        >
                            Correo Electrónico
                        </label>
                        <input
                            id="email"
                            v-model="form.email"
                            type="email"
                            required
                            autofocus
                            autocomplete="email"
                            class="w-full px-3 py-2.5 rounded-lg border border-gray-300 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#008c3a] focus:border-transparent transition-all text-sm"
                            placeholder="tu@email.com"
                        />
                        <div
                            v-if="form.errors.email"
                            class="mt-1.5 text-xs text-red-400"
                        >
                            {{ form.errors.email }}
                        </div>
                    </div>

                    <!-- Password -->
                    <div class="mb-4">
                        <label
                            for="password"
                            class="block text-sm font-medium text-gray-700 mb-1.5"
                        >
                            Contraseña
                        </label>
                        <input
                            id="password"
                            v-model="form.password"
                            :type="showPassword ? 'text' : 'password'"
                            required
                            autocomplete="current-password"
                            class="w-full px-3 py-2.5 rounded-lg border border-gray-300 bg-white text-gray-900 placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-[#008c3a] focus:border-transparent transition-all text-sm"
                            placeholder="••••••••"
                        />
                        <div
                            v-if="form.errors.password"
                            class="mt-1.5 text-xs text-red-400"
                        >
                            {{ form.errors.password }}
                        </div>
                    </div>

                    <!-- Ver Contraseña -->
                    <div class="mb-3 flex items-center">
                        <input
                            id="showPassword"
                            v-model="showPassword"
                            type="checkbox"
                            class="w-4 h-4 rounded border-gray-300 bg-white text-[#008c3a] focus:ring-[#008c3a] focus:ring-2"
                        />
                        <label
                            for="showPassword"
                            class="ml-2 text-sm text-gray-700"
                        >
                            Ver contraseña
                        </label>
                    </div>

                    <!-- Mantener sesión (cookie recordarme; recomendado en móvil/PWA) -->
                    <div class="mb-4 flex items-center">
                        <input
                            id="remember"
                            v-model="form.remember"
                            type="checkbox"
                            class="w-4 h-4 rounded border-gray-300 bg-white text-[#008c3a] focus:ring-[#008c3a] focus:ring-2"
                        />
                        <label
                            for="remember"
                            class="ml-2 text-sm text-gray-700"
                        >
                            Mantener la sesión iniciada al cerrar la aplicación
                        </label>
                    </div>

                    <!-- Submit Button -->
                    <button
                        type="submit"
                        :disabled="form.processing"
                        class="w-full py-2.5 px-4 bg-[#008c3a] hover:bg-[#006a2d] disabled:opacity-50 disabled:cursor-not-allowed text-white font-semibold rounded-lg transition-colors shadow-lg shadow-[#008c3a]/20 text-sm"
                    >
                        {{
                            form.processing
                                ? "Iniciando sesión..."
                                : "Iniciar Sesión"
                        }}
                    </button>
                </form>

                <!-- Link para recuperar contraseña -->
                <div class="mt-4 text-center">
                    <Link
                        :href="route('password.forgot')"
                        class="text-sm text-[#008c3a] hover:text-[#006a2d] hover:underline transition-colors"
                    >
                        ¿Olvidaste tu contraseña?
                    </Link>
                </div>

                <!-- Mensaje de éxito si viene de reset password -->
                <div
                    v-if="$page.props.flash?.success"
                    class="mt-4 p-3 rounded-lg bg-green-50 border border-green-200 text-green-800 text-sm"
                >
                    {{ $page.props.flash.success }}
                </div>

                <!-- Demo Credentials Hint -->

            </div>

            <!-- Footer -->
            <div class="mt-4 pt-3 border-t border-white/20">
                <p class="text-center text-xs text-white/90 font-light">
                    © 2025 Gobernación del Meta
                </p>
                <p class="text-center text-xs text-white/70 mt-0.5">
                    Todos los derechos reservados
                </p>
            </div>
        </div>

        <OfflineQrOverlay />
    </div>
</template>

<script setup>
import { ref } from "vue";
import { useForm, Link } from "@inertiajs/vue3";
import OfflineQrOverlay from "@/Components/OfflineQrOverlay.vue";

defineOptions({
    layout: null, // Sin layout para login
});

const showPassword = ref(false);

const form = useForm({
    email: "",
    password: "",
    remember: true,
});

const submit = () => {
    form.post(route("login"), {
        onFinish: () => form.reset("password"),
    });
};
</script>
