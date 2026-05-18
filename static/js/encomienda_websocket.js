class EncomiendaWebSocket {
    constructor(url, opciones = {}) {
        this.url = url;
        this.ws = null;

        this.intentos = 0;
        this.maxIntentos = opciones.maxIntentos || 10;
        this.baseDelay = opciones.baseDelay || 1000;
        this.maxDelay = opciones.maxDelay || 30000;

        this.conectadoDesde = null;
        this.tiempoConexionEstable = opciones.tiempoConexionEstable || 5000;

        this.badgeId = opciones.badgeId || 'ws-badge';

        this.onMensaje = opciones.onMensaje || function(data) {
            console.log('Mensaje WebSocket:', data);
        };

        this.onConectado = opciones.onConectado || function() {};
        this.onDesconectado = opciones.onDesconectado || function() {};
    }

    conectar() {
        if (
            this.ws &&
            (
                this.ws.readyState === WebSocket.OPEN ||
                this.ws.readyState === WebSocket.CONNECTING
            )
        ) {
            return;
        }

        this.ws = new WebSocket(this.url);

        this.ws.onopen = () => {
            console.log('Conectado');

            this.conectadoDesde = Date.now();

            this.actualizarBadge('EN VIVO', 'badge bg-success');

            this.onConectado(this.ws);
        };

        this.ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.onMensaje(data);
            } catch (error) {
                console.error('Mensaje WebSocket no es JSON válido:', event.data);
            }
        };

        this.ws.onclose = (event) => {
            console.log('WebSocket cerrado:', {
                code: event.code,
                reason: event.reason,
                wasClean: event.wasClean
            });

            this.onDesconectado(event);

            if (event.code === 4001) {
                this.actualizarBadge('No autorizado', 'badge bg-danger');
                window.location.href = '/login/';
                return;
            }

            if (event.code === 1000) {
                this.actualizarBadge('Desconectado', 'badge bg-secondary');
                return;
            }

            const duroConectado = this.conectadoDesde
                ? Date.now() - this.conectadoDesde
                : 0;

            if (duroConectado >= this.tiempoConexionEstable) {
                this.intentos = 0;
            }

            this.actualizarBadge('Reconectando...', 'badge bg-warning text-dark');

            const delay = Math.min(
                this.baseDelay * Math.pow(2, this.intentos),
                this.maxDelay
            );

            this.intentos++;

            if (this.intentos <= this.maxIntentos) {
                console.log(`Reconectando en ${delay / 1000}s (intento ${this.intentos})`);

                setTimeout(() => {
                    this.conectar();
                }, delay);
            } else {
                this.actualizarBadge('Desconectado', 'badge bg-danger');
            }
        };

        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }

    enviar(data) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            console.warn('WebSocket no está abierto. Mensaje no enviado:', data);
            return;
        }

        this.ws.send(JSON.stringify(data));
    }

    cerrar() {
        if (this.ws) {
            this.ws.close(1000, 'Cierre normal');
        }
    }

    actualizarBadge(texto, clases) {
        const badge = document.getElementById(this.badgeId);

        if (!badge) return;

        badge.textContent = texto;
        badge.className = clases;
    }
}