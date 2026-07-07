// Esquiva los Meteoritos — juego arcade táctil para celular.
// Sin dependencias: solo canvas 2D y eventos de puntero.

(() => {
  'use strict';

  const canvas = document.getElementById('game');
  const ctx = canvas.getContext('2d');

  let W = 0;
  let H = 0;
  let dpr = 1;

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener('resize', resize);
  resize();

  const STATE = { MENU: 0, PLAYING: 1, GAME_OVER: 2 };

  const game = {
    state: STATE.MENU,
    score: 0,
    best: Number(localStorage.getItem('meteoritos.best') || 0),
    speed: 1,
    ship: { x: 0, y: 0, r: 16, targetX: 0 },
    meteors: [],
    stars: [],
    particles: [],
    spawnTimer: 0,
    shakeTime: 0,
  };

  function makeStars() {
    game.stars = [];
    for (let i = 0; i < 60; i++) {
      game.stars.push({
        x: Math.random() * W,
        y: Math.random() * H,
        r: Math.random() * 1.5 + 0.5,
        v: Math.random() * 30 + 15,
      });
    }
  }
  makeStars();

  function reset() {
    game.score = 0;
    game.speed = 1;
    game.meteors = [];
    game.particles = [];
    game.spawnTimer = 0;
    game.ship.x = W / 2;
    game.ship.targetX = W / 2;
    game.ship.y = H - Math.max(90, H * 0.12);
  }

  // --- Entrada táctil / mouse ---
  function pointerX(e) {
    return (e.touches ? e.touches[0].clientX : e.clientX);
  }

  function onDown(e) {
    e.preventDefault();
    if (game.state === STATE.PLAYING) {
      game.ship.targetX = pointerX(e);
    } else {
      reset();
      game.state = STATE.PLAYING;
    }
  }

  function onMove(e) {
    e.preventDefault();
    if (game.state === STATE.PLAYING) {
      game.ship.targetX = pointerX(e);
    }
  }

  canvas.addEventListener('touchstart', onDown, { passive: false });
  canvas.addEventListener('touchmove', onMove, { passive: false });
  canvas.addEventListener('mousedown', onDown);
  canvas.addEventListener('mousemove', (e) => { if (e.buttons) onMove(e); });

  // --- Lógica ---
  function spawnMeteor() {
    const r = Math.random() * 18 + 10;
    game.meteors.push({
      x: Math.random() * (W - r * 2) + r,
      y: -r * 2,
      r,
      vy: (Math.random() * 80 + 140) * game.speed,
      vx: (Math.random() - 0.5) * 60,
      rot: Math.random() * Math.PI * 2,
      vrot: (Math.random() - 0.5) * 4,
      dodged: false,
    });
  }

  function explode(x, y, color, count) {
    for (let i = 0; i < count; i++) {
      const a = Math.random() * Math.PI * 2;
      const s = Math.random() * 180 + 40;
      game.particles.push({
        x, y,
        vx: Math.cos(a) * s,
        vy: Math.sin(a) * s,
        life: 1,
        color,
      });
    }
  }

  function update(dt) {
    for (const s of game.stars) {
      s.y += s.v * dt * (game.state === STATE.PLAYING ? game.speed : 1);
      if (s.y > H) { s.y = -2; s.x = Math.random() * W; }
    }

    for (let i = game.particles.length - 1; i >= 0; i--) {
      const p = game.particles[i];
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      p.life -= dt * 1.8;
      if (p.life <= 0) game.particles.splice(i, 1);
    }

    if (game.shakeTime > 0) game.shakeTime -= dt;
    if (game.state !== STATE.PLAYING) return;

    const ship = game.ship;
    ship.x += (ship.targetX - ship.x) * Math.min(1, dt * 14);
    ship.x = Math.max(ship.r, Math.min(W - ship.r, ship.x));

    game.speed += dt * 0.025;
    game.spawnTimer -= dt;
    if (game.spawnTimer <= 0) {
      spawnMeteor();
      game.spawnTimer = Math.max(0.25, 0.9 / game.speed);
    }

    for (let i = game.meteors.length - 1; i >= 0; i--) {
      const m = game.meteors[i];
      m.y += m.vy * dt;
      m.x += m.vx * dt;
      m.rot += m.vrot * dt;
      if (m.x < m.r || m.x > W - m.r) m.vx *= -1;

      if (!m.dodged && m.y - m.r > ship.y) {
        m.dodged = true;
        game.score++;
      }
      if (m.y - m.r > H) {
        game.meteors.splice(i, 1);
        continue;
      }

      const dx = m.x - ship.x;
      const dy = m.y - ship.y;
      if (dx * dx + dy * dy < (m.r + ship.r * 0.75) ** 2) {
        explode(ship.x, ship.y, '#7de3ff', 40);
        explode(m.x, m.y, '#ffb36b', 20);
        game.shakeTime = 0.4;
        game.state = STATE.GAME_OVER;
        if (game.score > game.best) {
          game.best = game.score;
          localStorage.setItem('meteoritos.best', String(game.best));
        }
      }
    }
  }

  // --- Dibujo ---
  function drawShip(x, y, r) {
    ctx.save();
    ctx.translate(x, y);
    // Llama del propulsor
    const flame = Math.random() * 10 + 12;
    ctx.beginPath();
    ctx.moveTo(-r * 0.4, r * 0.8);
    ctx.lineTo(0, r * 0.8 + flame);
    ctx.lineTo(r * 0.4, r * 0.8);
    ctx.closePath();
    ctx.fillStyle = '#ff9d4d';
    ctx.fill();
    // Cuerpo
    ctx.beginPath();
    ctx.moveTo(0, -r);
    ctx.lineTo(r * 0.85, r * 0.8);
    ctx.lineTo(0, r * 0.4);
    ctx.lineTo(-r * 0.85, r * 0.8);
    ctx.closePath();
    ctx.fillStyle = '#7de3ff';
    ctx.fill();
    // Cabina
    ctx.beginPath();
    ctx.arc(0, -r * 0.2, r * 0.28, 0, Math.PI * 2);
    ctx.fillStyle = '#0b0e1a';
    ctx.fill();
    ctx.restore();
  }

  function drawMeteor(m) {
    ctx.save();
    ctx.translate(m.x, m.y);
    ctx.rotate(m.rot);
    ctx.beginPath();
    const spikes = 8;
    for (let i = 0; i < spikes; i++) {
      const a = (i / spikes) * Math.PI * 2;
      const rr = m.r * (i % 2 === 0 ? 1 : 0.8);
      ctx.lineTo(Math.cos(a) * rr, Math.sin(a) * rr);
    }
    ctx.closePath();
    ctx.fillStyle = '#a8794f';
    ctx.fill();
    ctx.beginPath();
    ctx.arc(-m.r * 0.3, -m.r * 0.2, m.r * 0.22, 0, Math.PI * 2);
    ctx.fillStyle = '#7c5837';
    ctx.fill();
    ctx.restore();
  }

  function drawText(text, x, y, size, color, align = 'center') {
    ctx.fillStyle = color;
    ctx.font = `bold ${size}px system-ui, sans-serif`;
    ctx.textAlign = align;
    ctx.textBaseline = 'middle';
    ctx.fillText(text, x, y);
  }

  function draw() {
    ctx.save();
    if (game.shakeTime > 0) {
      ctx.translate((Math.random() - 0.5) * 10, (Math.random() - 0.5) * 10);
    }

    ctx.fillStyle = '#0b0e1a';
    ctx.fillRect(-20, -20, W + 40, H + 40);

    ctx.fillStyle = '#ffffff';
    for (const s of game.stars) {
      ctx.globalAlpha = 0.4 + s.r * 0.3;
      ctx.fillRect(s.x, s.y, s.r, s.r * 2);
    }
    ctx.globalAlpha = 1;

    for (const m of game.meteors) drawMeteor(m);

    for (const p of game.particles) {
      ctx.globalAlpha = Math.max(0, p.life);
      ctx.fillStyle = p.color;
      ctx.fillRect(p.x - 2, p.y - 2, 4, 4);
    }
    ctx.globalAlpha = 1;

    if (game.state !== STATE.GAME_OVER) {
      drawShip(game.ship.x, game.ship.y, game.ship.r);
    }

    if (game.state === STATE.PLAYING) {
      drawText(String(game.score), W / 2, 50, 42, '#ffffff');
    } else if (game.state === STATE.MENU) {
      drawText('ESQUIVA LOS', W / 2, H * 0.32, 34, '#7de3ff');
      drawText('METEORITOS', W / 2, H * 0.32 + 42, 34, '#7de3ff');
      drawText('Arrastra el dedo para mover la nave', W / 2, H * 0.5, 16, '#ffffff');
      drawText('Toca para empezar', W / 2, H * 0.58, 18, '#ffd166');
      if (game.best > 0) {
        drawText(`Récord: ${game.best}`, W / 2, H * 0.66, 16, '#9aa4c0');
      }
    } else if (game.state === STATE.GAME_OVER) {
      drawText('¡PERDISTE!', W / 2, H * 0.35, 38, '#ff6b6b');
      drawText(`Puntos: ${game.score}`, W / 2, H * 0.45, 24, '#ffffff');
      drawText(`Récord: ${game.best}`, W / 2, H * 0.52, 18, '#9aa4c0');
      drawText('Toca para reintentar', W / 2, H * 0.62, 18, '#ffd166');
    }

    ctx.restore();
  }

  let last = performance.now();
  function loop(now) {
    const dt = Math.min((now - last) / 1000, 0.05);
    last = now;
    update(dt);
    draw();
    requestAnimationFrame(loop);
  }

  game.ship.x = W / 2;
  game.ship.targetX = W / 2;
  game.ship.y = H - Math.max(90, H * 0.12);
  requestAnimationFrame(loop);
})();
