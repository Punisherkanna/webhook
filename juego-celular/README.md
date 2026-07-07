# Juego para Celular 🎮

Juego arcade HTML5 para celular: **Esquiva los Meteoritos**. Controlas una nave con el dedo y esquivas meteoritos que caen cada vez más rápido.

Funciona en cualquier navegador móvil (y también en escritorio con el mouse). No requiere instalación, dependencias ni servidor especial.

## Cómo jugar

- **Arrastra el dedo** (o el mouse) para mover la nave.
- Esquiva los meteoritos: si te golpean, pierdes.
- Cada meteorito esquivado suma puntos y la velocidad aumenta.
- Toca la pantalla para reiniciar después de perder.

## Cómo ejecutarlo

Opción 1 — abrir directamente:

```
Abre index.html en el navegador
```

Opción 2 — servidor local (recomendado para probar en el celular desde la misma red):

```bash
cd juego-celular
python3 -m http.server 8000
# En el celular: http://<IP-de-tu-PC>:8000
```

## Estructura

```
juego-celular/
├── index.html   # Página y estilos
├── game.js      # Lógica del juego (canvas, táctil, puntaje)
└── README.md
```

## Nota sobre el repositorio

Este proyecto está pensado para vivir en su propio repositorio. La integración de esta sesión no tiene permisos para crear repositorios nuevos, así que el proyecto se inició aquí. Para migrarlo:

1. Crea un repositorio nuevo en GitHub (por ejemplo `juego-celular`).
2. Copia el contenido de esta carpeta al nuevo repo.
