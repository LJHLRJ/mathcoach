"""可选的动态背景；仅在仪表盘/空状态使用。

Shader HTML 来自 Radiant（MIT，Copyright (c) 2025 Paul Bakaus）：
https://github.com/pbakaus/radiant
commit 59e9f48c0ad9a3db2fbeb8898b4390d5a1eabb40
static/flow-field.html（10,086 字节）
static/topographic.html（16,179 字节）

仅以内联常量注入，不加载外部图片或脚本；不拼接用户输入。
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import streamlit as st

from ..config import db_path
from ..domain.models import Consent
from ..memory.settings_repo import SQLiteSettingsStore

DYNAMIC_BACKGROUND_KEY = "dynamic_background_enabled"

_PRELUDE = """
<style>
html, body { background: #0b0b0c !important; }
canvas { opacity: 0.25 !important; }
@media (prefers-reduced-motion: reduce) {
  canvas { display: none !important; }
}
</style>
<script>
(function () {
  if (
    window.matchMedia &&
    window.matchMedia('(prefers-reduced-motion: reduce)').matches
  ) {
    window.requestAnimationFrame = function () { return 0; };
  }
})();
</script>
"""

SHADER_HTML = {
    "dashboard": r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Topographic Contour Map</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; overflow: hidden; background: #0a0a0a; }
  canvas { display: block; width: 100vw; height: 100vh; }
  .label {
    position: fixed;
    top: 20px;
    left: 24px;
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 11px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: rgba(200, 149, 108, 0.5);
    z-index: 10;
    pointer-events: none;
    user-select: none;
  }
</style>
</head>
<body>
<div class="label">Topographic</div>
<canvas id="canvas"></canvas>
<script>
// ─────────────────────────────────────────────
// Simplex Noise (same compact implementation)
// ─────────────────────────────────────────────
const SimplexNoise = (function() {
  const F2 = 0.5 * (Math.sqrt(3) - 1);
  const G2 = (3 - Math.sqrt(3)) / 6;
  const F3 = 1 / 3;
  const G3 = 1 / 6;

  const grad3 = [
    [1,1,0],[-1,1,0],[1,-1,0],[-1,-1,0],
    [1,0,1],[-1,0,1],[1,0,-1],[-1,0,-1],
    [0,1,1],[0,-1,1],[0,1,-1],[0,-1,-1]
  ];

  function SimplexNoise(seed) {
    this.perm = new Uint8Array(512);
    this.permMod12 = new Uint8Array(512);
    const p = new Uint8Array(256);
    seed = seed || Math.random() * 65536;
    for (let i = 0; i < 256; i++) p[i] = i;
    for (let i = 255; i > 0; i--) {
      seed = (seed * 16807 + 0) % 2147483647;
      const j = seed % (i + 1);
      const tmp = p[i];
      p[i] = p[j];
      p[j] = tmp;
    }
    for (let i = 0; i < 512; i++) {
      this.perm[i] = p[i & 255];
      this.permMod12[i] = this.perm[i] % 12;
    }
  }

  SimplexNoise.prototype.noise3D = function(xin, yin, zin) {
    const perm = this.perm, permMod12 = this.permMod12;
    let n0, n1, n2, n3;
    const s = (xin + yin + zin) * F3;
    const i = Math.floor(xin + s), j = Math.floor(yin + s), k = Math.floor(zin + s);
    const t = (i + j + k) * G3;
    const X0 = i - t, Y0 = j - t, Z0 = k - t;
    const x0 = xin - X0, y0 = yin - Y0, z0 = zin - Z0;
    let i1, j1, k1, i2, j2, k2;
    if (x0 >= y0) {
      if (y0 >= z0) { i1=1;j1=0;k1=0;i2=1;j2=1;k2=0; }
      else if (x0 >= z0) { i1=1;j1=0;k1=0;i2=1;j2=0;k2=1; }
      else { i1=0;j1=0;k1=1;i2=1;j2=0;k2=1; }
    } else {
      if (y0 < z0) { i1=0;j1=0;k1=1;i2=0;j2=1;k2=1; }
      else if (x0 < z0) { i1=0;j1=1;k1=0;i2=0;j2=1;k2=1; }
      else { i1=0;j1=1;k1=0;i2=1;j2=1;k2=0; }
    }
    const x1 = x0 - i1 + G3, y1 = y0 - j1 + G3, z1 = z0 - k1 + G3;
    const x2 = x0 - i2 + 2*G3, y2 = y0 - j2 + 2*G3, z2 = z0 - k2 + 2*G3;
    const x3 = x0 - 1 + 3*G3, y3 = y0 - 1 + 3*G3, z3 = z0 - 1 + 3*G3;
    const ii = i & 255, jj = j & 255, kk = k & 255;
    let t0 = 0.6 - x0*x0 - y0*y0 - z0*z0;
    if (t0 < 0) n0 = 0;
    else { t0 *= t0; const gi = permMod12[ii+perm[jj+perm[kk]]]; n0 = t0*t0*(grad3[gi][0]*x0+grad3[gi][1]*y0+grad3[gi][2]*z0); }
    let t1 = 0.6 - x1*x1 - y1*y1 - z1*z1;
    if (t1 < 0) n1 = 0;
    else { t1 *= t1; const gi = permMod12[ii+i1+perm[jj+j1+perm[kk+k1]]]; n1 = t1*t1*(grad3[gi][0]*x1+grad3[gi][1]*y1+grad3[gi][2]*z1); }
    let t2 = 0.6 - x2*x2 - y2*y2 - z2*z2;
    if (t2 < 0) n2 = 0;
    else { t2 *= t2; const gi = permMod12[ii+i2+perm[jj+j2+perm[kk+k2]]]; n2 = t2*t2*(grad3[gi][0]*x2+grad3[gi][1]*y2+grad3[gi][2]*z2); }
    let t3 = 0.6 - x3*x3 - y3*y3 - z3*z3;
    if (t3 < 0) n3 = 0;
    else { t3 *= t3; const gi = permMod12[ii+1+perm[jj+1+perm[kk+1]]]; n3 = t3*t3*(grad3[gi][0]*x3+grad3[gi][1]*y3+grad3[gi][2]*z3); }
    return 32 * (n0 + n1 + n2 + n3);
  };

  return SimplexNoise;
})();

// ─────────────────────────────────────────────
// Topographic Contour Renderer
// ─────────────────────────────────────────────
(function() {
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');
  const noise = new SimplexNoise(73);
  const dpr = window.devicePixelRatio || 1;

  let W, H;
  let field = new Float32Array(0);
  let fieldCols = 0;
  let fieldRows = 0;

  function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  window.addEventListener('resize', resize);
  resize();

  function ensureField(cols, rows) {
    if (cols !== fieldCols || rows !== fieldRows) {
      fieldCols = cols;
      fieldRows = rows;
      field = new Float32Array(cols * rows);
    }
  }

  // ── Noise sampling with octaves ──
  function fbm(x, y, z) {
    let val = 0;
    let amp = 1;
    let freq = 1;
    let sum = 0;
    for (let o = 0; o < 4; o++) {
      val += noise.noise3D(x * freq, y * freq, z) * amp;
      sum += amp;
      amp *= 0.5;
      freq *= 2;
    }
    return val / sum;
  }

  // ── Color helpers ──
  const colors = {
    amber: { r: 200, g: 149, b: 108 },
    gold:  { r: 212, g: 165, b: 116 },
    coral: { r: 224, g: 120, b: 80 },
  };

  function rgba(c, a) {
    return 'rgba(' + c.r + ',' + c.g + ',' + c.b + ',' + a + ')';
  }

  function lerpC(a, b, t) {
    return {
      r: Math.round(a.r + (b.r - a.r) * t),
      g: Math.round(a.g + (b.g - a.g) * t),
      b: Math.round(a.b + (b.b - a.b) * t)
    };
  }

  // ── Marching squares isoline extraction ──
  // Each cell has 4 corners; we check which are above/below the threshold
  // and interpolate edge crossings to produce line segments.

  // Edge interpolation: find the point between two values where the threshold is crossed
  function interp(v1, v2, threshold) {
    if (Math.abs(v2 - v1) < 0.0001) return 0.5;
    return (threshold - v1) / (v2 - v1);
  }

  // Marching squares lookup — maps 4-bit case index to list of edge pairs
  // Edges: 0=top, 1=right, 2=bottom, 3=left
  const EDGE_TABLE = [
    [],            // 0000
    [[3, 2]],      // 0001
    [[2, 1]],      // 0010
    [[3, 1]],      // 0011
    [[1, 0]],      // 0100
    [[1, 0],[3, 2]], // 0101 (saddle)
    [[2, 0]],      // 0110
    [[3, 0]],      // 0111
    [[0, 3]],      // 1000
    [[0, 2]],      // 1001
    [[0, 3],[2, 1]], // 1010 (saddle)
    [[0, 1]],      // 1011
    [[1, 3]],      // 1100
    [[1, 2]],      // 1101
    [[2, 3]],      // 1110
    []             // 1111
  ];

  // Given edge index and interpolation values, return the (x, y) point on that edge
  function edgePoint(edge, cx, cy, cellW, cellH, tl, tr, br, bl, threshold) {
    let t;
    switch (edge) {
      case 0: // top edge (tl -> tr)
        t = interp(tl, tr, threshold);
        return [cx + t * cellW, cy];
      case 1: // right edge (tr -> br)
        t = interp(tr, br, threshold);
        return [cx + cellW, cy + t * cellH];
      case 2: // bottom edge (bl -> br)
        t = interp(bl, br, threshold);
        return [cx + t * cellW, cy + cellH];
      case 3: // left edge (tl -> bl)
        t = interp(tl, bl, threshold);
        return [cx, cy + t * cellH];
    }
  }

  // ── Configuration ──
  const CELL_SIZE = 8;          // Grid cell size in pixels
  let NUM_CONTOURS = 14;        // Number of contour levels
  const NOISE_SCALE = 0.003;    // Scale of noise field
  let TIME_SPEED = 0.15;        // How fast the field evolves
  const LABEL_DENSITY = 0.003;  // Probability of placing elevation label per segment

  // ── Elevation labels ──
  // We'll collect candidate positions during contour extraction and draw labels
  let labelCandidates = [];

  // ── Mouse state ──
  let mouseX = 0, mouseY = 0;
  let mouseActive = false;
  let mouseDown = false;

  canvas.addEventListener('mousemove', function(e) { mouseX = e.clientX; mouseY = e.clientY; mouseActive = true; });
  canvas.addEventListener('mouseleave', function() { mouseActive = false; });
  canvas.addEventListener('mousedown', function(e) { mouseDown = true; mouseX = e.clientX; mouseY = e.clientY; mouseActive = true; });
  canvas.addEventListener('mouseup', function() { mouseDown = false; });
  canvas.addEventListener('touchstart', function(e) { e.preventDefault(); mouseDown = true; mouseActive = true; mouseX = e.touches[0].clientX; mouseY = e.touches[0].clientY; }, { passive: false });
  canvas.addEventListener('touchmove', function(e) { e.preventDefault(); mouseX = e.touches[0].clientX; mouseY = e.touches[0].clientY; }, { passive: false });
  canvas.addEventListener('touchend', function() { mouseDown = false; mouseActive = false; });

  // ── Animation ──
  let time = 0;
  let lastTime = 0;

  function draw(timestamp) {
    if (!lastTime) lastTime = timestamp;
    const dt = (timestamp - lastTime) / 1000;
    lastTime = timestamp;
    time += dt * TIME_SPEED;

    // Clear
    ctx.fillStyle = '#0a0a0a';
    ctx.fillRect(0, 0, W, H);

    const cols = Math.ceil(W / CELL_SIZE) + 1;
    const rows = Math.ceil(H / CELL_SIZE) + 1;
    ensureField(cols, rows);

    // Sample the noise field into a grid
    for (let j = 0; j < rows; j++) {
      for (let i = 0; i < cols; i++) {
        const x = i * CELL_SIZE;
        const y = j * CELL_SIZE;
        let val = fbm(x * NOISE_SCALE, y * NOISE_SCALE, time);
        // Mouse adds an elevation peak (or valley when clicking)
        if (mouseActive) {
          const mdx = x - mouseX;
          const mdy = y - mouseY;
          const md = Math.sqrt(mdx * mdx + mdy * mdy);
          const radius = Math.min(W, H) * 0.2;
          if (md < radius) {
            const falloff = 1 - md / radius;
            val += (mouseDown ? -0.5 : 0.5) * falloff * falloff;
          }
        }
        field[j * cols + i] = val;
      }
    }

    // Find min/max for normalization
    let minVal = Infinity, maxVal = -Infinity;
    for (let k = 0; k < field.length; k++) {
      if (field[k] < minVal) minVal = field[k];
      if (field[k] > maxVal) maxVal = field[k];
    }
    const range = maxVal - minVal || 1;

    // Normalize field to 0..1
    for (let k = 0; k < field.length; k++) {
      field[k] = (field[k] - minVal) / range;
    }

    labelCandidates = [];

    // Draw contours
    for (let c = 0; c < NUM_CONTOURS; c++) {
      const threshold = (c + 1) / (NUM_CONTOURS + 1);

      // Color: blend from deep coral (low) through amber (mid) to gold (high)
      let lineColor;
      if (threshold < 0.5) {
        lineColor = lerpC(colors.coral, colors.amber, threshold * 2);
      } else {
        lineColor = lerpC(colors.amber, colors.gold, (threshold - 0.5) * 2);
      }

      // Opacity varies: stronger in the middle, subtler at extremes
      const distFromCenter = Math.abs(threshold - 0.5) * 2; // 0 at center, 1 at edges
      const baseAlpha = 0.25 + (1 - distFromCenter) * 0.45;

      // Every 5th contour is a "major" contour — thicker and brighter
      const isMajor = (c % 5 === 0);
      const glowWidth = isMajor ? 4.5 : 2.5;
      const sharpWidth = isMajor ? 1.2 : 0.6;
      const glowAlpha = baseAlpha * 0.25;
      const sharpAlpha = baseAlpha * (isMajor ? 1.0 : 0.8);

      // Build line segments for this contour level
      const segments = [];

      for (let j = 0; j < rows - 1; j++) {
        for (let i = 0; i < cols - 1; i++) {
          const tl = field[j * cols + i];
          const tr = field[j * cols + i + 1];
          const br = field[(j + 1) * cols + i + 1];
          const bl = field[(j + 1) * cols + i];

          // 4-bit case index
          const caseIdx =
            (tl >= threshold ? 8 : 0) |
            (tr >= threshold ? 4 : 0) |
            (br >= threshold ? 2 : 0) |
            (bl >= threshold ? 1 : 0);

          const edges = EDGE_TABLE[caseIdx];
          if (!edges || edges.length === 0) continue;

          const cx = i * CELL_SIZE;
          const cy = j * CELL_SIZE;

          for (let e = 0; e < edges.length; e++) {
            const p1 = edgePoint(edges[e][0], cx, cy, CELL_SIZE, CELL_SIZE, tl, tr, br, bl, threshold);
            const p2 = edgePoint(edges[e][1], cx, cy, CELL_SIZE, CELL_SIZE, tl, tr, br, bl, threshold);
            segments.push(p1[0], p1[1], p2[0], p2[1]);

            // Candidate for elevation label
            if (isMajor && Math.random() < LABEL_DENSITY) {
              const mx = (p1[0] + p2[0]) * 0.5;
              const my = (p1[1] + p2[1]) * 0.5;
              const angle = Math.atan2(p2[1] - p1[1], p2[0] - p1[0]);
              labelCandidates.push({
                x: mx, y: my,
                angle: angle,
                elevation: Math.round(threshold * 1000),
                color: lineColor,
                alpha: sharpAlpha * 0.6
              });
            }
          }
        }
      }

      // Draw glow pass (thick, low alpha)
      if (segments.length > 0) {
        ctx.beginPath();
        for (let s = 0; s < segments.length; s += 4) {
          ctx.moveTo(segments[s], segments[s+1]);
          ctx.lineTo(segments[s+2], segments[s+3]);
        }
        ctx.strokeStyle = rgba(lineColor, glowAlpha);
        ctx.lineWidth = glowWidth;
        ctx.lineCap = 'round';
        ctx.stroke();

        // Draw sharp pass (thin, high alpha)
        ctx.beginPath();
        for (let s = 0; s < segments.length; s += 4) {
          ctx.moveTo(segments[s], segments[s+1]);
          ctx.lineTo(segments[s+2], segments[s+3]);
        }
        ctx.strokeStyle = rgba(lineColor, sharpAlpha);
        ctx.lineWidth = sharpWidth;
        ctx.lineCap = 'round';
        ctx.stroke();
      }
    }

    // ── Draw elevation labels ──
    // Filter out labels that are too close to each other
    const MIN_LABEL_DIST = 120;
    const filteredLabels = [];
    for (let i = 0; i < labelCandidates.length; i++) {
      const lbl = labelCandidates[i];
      // Skip labels near edges
      if (lbl.x < 80 || lbl.x > W - 80 || lbl.y < 40 || lbl.y > H - 40) continue;
      let tooClose = false;
      for (let j = 0; j < filteredLabels.length; j++) {
        const dx = lbl.x - filteredLabels[j].x;
        const dy = lbl.y - filteredLabels[j].y;
        if (dx * dx + dy * dy < MIN_LABEL_DIST * MIN_LABEL_DIST) {
          tooClose = true;
          break;
        }
      }
      if (!tooClose) filteredLabels.push(lbl);
    }

    ctx.font = '9px "SF Mono", "Fira Code", "Cascadia Code", monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    for (let i = 0; i < filteredLabels.length; i++) {
      const lbl = filteredLabels[i];
      const text = lbl.elevation.toString();
      const tw = ctx.measureText(text).width + 6;

      ctx.save();
      ctx.translate(lbl.x, lbl.y);

      // Keep text roughly horizontal for readability
      let angle = lbl.angle;
      if (angle > Math.PI / 2) angle -= Math.PI;
      if (angle < -Math.PI / 2) angle += Math.PI;
      ctx.rotate(angle);

      // Background knockout — small dark rectangle behind text
      ctx.fillStyle = 'rgba(10, 10, 10, 0.85)';
      ctx.fillRect(-tw / 2, -6, tw, 12);

      // Text
      ctx.fillStyle = rgba(lbl.color, lbl.alpha);
      ctx.fillText(text, 0, 0.5);

      ctx.restore();
    }

    // ── Subtle vignette overlay ──
    const vGrad = ctx.createRadialGradient(W/2, H/2, Math.min(W, H) * 0.3, W/2, H/2, Math.max(W, H) * 0.75);
    vGrad.addColorStop(0, 'rgba(10,10,10,0)');
    vGrad.addColorStop(1, 'rgba(10,10,10,0.4)');
    ctx.fillStyle = vGrad;
    ctx.fillRect(0, 0, W, H);

    requestAnimationFrame(draw);
  }

  requestAnimationFrame(draw);

  window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'param') {
      switch (e.data.name) {
        case 'NUM_CONTOURS': NUM_CONTOURS = Math.round(e.data.value); break;
        case 'TIME_SPEED': TIME_SPEED = e.data.value; break;
      }
    }
  });
})();
</script>
</body>
</html>
''',
    "empty": r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Flow Field with Particle Trails</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; overflow: hidden; background: #0a0a0a; }
  canvas { display: block; width: 100vw; height: 100vh; }
  .label {
    position: fixed;
    top: 20px;
    left: 24px;
    font-family: 'SF Mono', 'Fira Code', 'Cascadia Code', monospace;
    font-size: 11px;
    letter-spacing: 0.15em;
    text-transform: uppercase;
    color: rgba(200, 149, 108, 0.5);
    z-index: 10;
    pointer-events: none;
    user-select: none;
  }
</style>
</head>
<body>
<div class="label">Flow Field</div>
<canvas id="canvas"></canvas>
<script>
// ─────────────────────────────────────────────
// Simplex Noise (compact implementation)
// Based on Stefan Gustavson's simplex noise
// ─────────────────────────────────────────────
const SimplexNoise = (function() {
  const F2 = 0.5 * (Math.sqrt(3) - 1);
  const G2 = (3 - Math.sqrt(3)) / 6;
  const F3 = 1 / 3;
  const G3 = 1 / 6;

  const grad3 = [
    [1,1,0],[-1,1,0],[1,-1,0],[-1,-1,0],
    [1,0,1],[-1,0,1],[1,0,-1],[-1,0,-1],
    [0,1,1],[0,-1,1],[0,1,-1],[0,-1,-1]
  ];

  function SimplexNoise(seed) {
    this.perm = new Uint8Array(512);
    this.permMod12 = new Uint8Array(512);
    const p = new Uint8Array(256);
    // Seed-based permutation
    seed = seed || Math.random() * 65536;
    for (let i = 0; i < 256; i++) p[i] = i;
    for (let i = 255; i > 0; i--) {
      seed = (seed * 16807 + 0) % 2147483647;
      const j = seed % (i + 1);
      const tmp = p[i];
      p[i] = p[j];
      p[j] = tmp;
    }
    for (let i = 0; i < 512; i++) {
      this.perm[i] = p[i & 255];
      this.permMod12[i] = this.perm[i] % 12;
    }
  }

  SimplexNoise.prototype.noise2D = function(xin, yin) {
    const perm = this.perm, permMod12 = this.permMod12;
    let n0, n1, n2;
    const s = (xin + yin) * F2;
    const i = Math.floor(xin + s);
    const j = Math.floor(yin + s);
    const t = (i + j) * G2;
    const X0 = i - t, Y0 = j - t;
    const x0 = xin - X0, y0 = yin - Y0;
    let i1, j1;
    if (x0 > y0) { i1 = 1; j1 = 0; }
    else { i1 = 0; j1 = 1; }
    const x1 = x0 - i1 + G2, y1 = y0 - j1 + G2;
    const x2 = x0 - 1 + 2 * G2, y2 = y0 - 1 + 2 * G2;
    const ii = i & 255, jj = j & 255;
    let t0 = 0.5 - x0*x0 - y0*y0;
    if (t0 < 0) n0 = 0;
    else { t0 *= t0; const gi = permMod12[ii + perm[jj]]; n0 = t0 * t0 * (grad3[gi][0]*x0 + grad3[gi][1]*y0); }
    let t1 = 0.5 - x1*x1 - y1*y1;
    if (t1 < 0) n1 = 0;
    else { t1 *= t1; const gi = permMod12[ii + i1 + perm[jj + j1]]; n1 = t1 * t1 * (grad3[gi][0]*x1 + grad3[gi][1]*y1); }
    let t2 = 0.5 - x2*x2 - y2*y2;
    if (t2 < 0) n2 = 0;
    else { t2 *= t2; const gi = permMod12[ii + 1 + perm[jj + 1]]; n2 = t2 * t2 * (grad3[gi][0]*x2 + grad3[gi][1]*y2); }
    return 70 * (n0 + n1 + n2);
  };

  SimplexNoise.prototype.noise3D = function(xin, yin, zin) {
    const perm = this.perm, permMod12 = this.permMod12;
    let n0, n1, n2, n3;
    const s = (xin + yin + zin) * F3;
    const i = Math.floor(xin + s), j = Math.floor(yin + s), k = Math.floor(zin + s);
    const t = (i + j + k) * G3;
    const X0 = i - t, Y0 = j - t, Z0 = k - t;
    const x0 = xin - X0, y0 = yin - Y0, z0 = zin - Z0;
    let i1, j1, k1, i2, j2, k2;
    if (x0 >= y0) {
      if (y0 >= z0) { i1=1;j1=0;k1=0;i2=1;j2=1;k2=0; }
      else if (x0 >= z0) { i1=1;j1=0;k1=0;i2=1;j2=0;k2=1; }
      else { i1=0;j1=0;k1=1;i2=1;j2=0;k2=1; }
    } else {
      if (y0 < z0) { i1=0;j1=0;k1=1;i2=0;j2=1;k2=1; }
      else if (x0 < z0) { i1=0;j1=1;k1=0;i2=0;j2=1;k2=1; }
      else { i1=0;j1=1;k1=0;i2=1;j2=1;k2=0; }
    }
    const x1 = x0 - i1 + G3, y1 = y0 - j1 + G3, z1 = z0 - k1 + G3;
    const x2 = x0 - i2 + 2*G3, y2 = y0 - j2 + 2*G3, z2 = z0 - k2 + 2*G3;
    const x3 = x0 - 1 + 3*G3, y3 = y0 - 1 + 3*G3, z3 = z0 - 1 + 3*G3;
    const ii = i & 255, jj = j & 255, kk = k & 255;
    let t0 = 0.6 - x0*x0 - y0*y0 - z0*z0;
    if (t0 < 0) n0 = 0;
    else { t0 *= t0; const gi = permMod12[ii+perm[jj+perm[kk]]]; n0 = t0*t0*(grad3[gi][0]*x0+grad3[gi][1]*y0+grad3[gi][2]*z0); }
    let t1 = 0.6 - x1*x1 - y1*y1 - z1*z1;
    if (t1 < 0) n1 = 0;
    else { t1 *= t1; const gi = permMod12[ii+i1+perm[jj+j1+perm[kk+k1]]]; n1 = t1*t1*(grad3[gi][0]*x1+grad3[gi][1]*y1+grad3[gi][2]*z1); }
    let t2 = 0.6 - x2*x2 - y2*y2 - z2*z2;
    if (t2 < 0) n2 = 0;
    else { t2 *= t2; const gi = permMod12[ii+i2+perm[jj+j2+perm[kk+k2]]]; n2 = t2*t2*(grad3[gi][0]*x2+grad3[gi][1]*y2+grad3[gi][2]*z2); }
    let t3 = 0.6 - x3*x3 - y3*y3 - z3*z3;
    if (t3 < 0) n3 = 0;
    else { t3 *= t3; const gi = permMod12[ii+1+perm[jj+1+perm[kk+1]]]; n3 = t3*t3*(grad3[gi][0]*x3+grad3[gi][1]*y3+grad3[gi][2]*z3); }
    return 32 * (n0 + n1 + n2 + n3);
  };

  return SimplexNoise;
})();

// ─────────────────────────────────────────────
// Flow Field Renderer
// ─────────────────────────────────────────────
(function() {
  const canvas = document.getElementById('canvas');
  const ctx = canvas.getContext('2d');
  const noise = new SimplexNoise(42);
  const dpr = window.devicePixelRatio || 1;

  let W, H;

  function resize() {
    W = window.innerWidth;
    H = window.innerHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    // Fill with background on resize to avoid flash
    ctx.fillStyle = '#0a0a0a';
    ctx.fillRect(0, 0, W, H);
  }

  window.addEventListener('resize', resize);
  resize();

  // ── Mouse tracking ──
  const mouse = { x: -9999, y: -9999, active: false };
  window.addEventListener('mousemove', function(e) {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
    mouse.active = true;
  });
  window.addEventListener('mouseleave', function() {
    mouse.active = false;
  });

  // ── Color palette ──
  // Warm tones: amber, gold, coral, with variations
  const palette = [
    { r: 200, g: 149, b: 108 }, // amber  #c8956c
    { r: 212, g: 165, b: 116 }, // gold   #d4a574
    { r: 224, g: 120, b: 80  }, // coral  #e07850
    { r: 190, g: 130, b: 90  }, // dark amber
    { r: 230, g: 180, b: 140 }, // light gold
    { r: 210, g: 100, b: 70  }, // deep coral
    { r: 180, g: 160, b: 120 }, // muted gold
  ];

  function lerpColor(a, b, t) {
    return {
      r: a.r + (b.r - a.r) * t,
      g: a.g + (b.g - a.g) * t,
      b: a.b + (b.b - a.b) * t
    };
  }

  function getColor(noiseVal) {
    // Map noise [-1,1] to palette index
    const t = (noiseVal + 1) * 0.5; // 0..1
    const idx = t * (palette.length - 1);
    const i = Math.floor(idx);
    const f = idx - i;
    const a = palette[Math.min(i, palette.length - 1)];
    const b = palette[Math.min(i + 1, palette.length - 1)];
    return lerpColor(a, b, f);
  }

  // ── Particles ──
  const PARTICLE_COUNT = 2500;
  let NOISE_SCALE = 0.0025;
  let SPEED = 1.2;
  const MOUSE_RADIUS = 150;
  const MOUSE_FORCE = 2.5;

  const particles = [];

  function createParticle() {
    return {
      x: Math.random() * W,
      y: Math.random() * H,
      speed: 0.4 + Math.random() * 1.0,
      alpha: 0.15 + Math.random() * 0.55,
      size: 0.5 + Math.random() * 1.5
    };
  }

  for (let i = 0; i < PARTICLE_COUNT; i++) {
    particles.push(createParticle());
  }

  // ── Animation ──
  let time = 0;

  function draw() {
    // Fade previous frame with dark overlay — creates trailing effect
    ctx.fillStyle = 'rgba(10, 10, 10, 0.03)';
    ctx.fillRect(0, 0, W, H);

    time += 0.0008;

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const p = particles[i];

      // Sample noise field at particle position with time evolution
      const nx = p.x * NOISE_SCALE;
      const ny = p.y * NOISE_SCALE;
      const angle = noise.noise3D(nx, ny, time) * Math.PI * 2;

      // Secondary noise for color variation
      const colorNoise = noise.noise3D(nx * 1.5 + 100, ny * 1.5 + 100, time * 0.5);

      // Velocity from flow field
      let vx = Math.cos(angle) * p.speed * SPEED;
      let vy = Math.sin(angle) * p.speed * SPEED;

      // Mouse interaction — gentle push away
      if (mouse.active) {
        const dx = p.x - mouse.x;
        const dy = p.y - mouse.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < MOUSE_RADIUS && dist > 0) {
          const force = (1 - dist / MOUSE_RADIUS) * MOUSE_FORCE;
          vx += (dx / dist) * force;
          vy += (dy / dist) * force;
        }
      }

      // Store previous position for line drawing
      const px = p.x;
      const py = p.y;

      // Update position
      p.x += vx;
      p.y += vy;

      // Draw particle trail segment
      const color = getColor(colorNoise);
      ctx.beginPath();
      ctx.moveTo(px, py);
      ctx.lineTo(p.x, p.y);
      ctx.strokeStyle = 'rgba(' + Math.round(color.r) + ',' + Math.round(color.g) + ',' + Math.round(color.b) + ',' + p.alpha + ')';
      ctx.lineWidth = p.size;
      ctx.stroke();

      // Respawn if offscreen
      if (p.x < -20 || p.x > W + 20 || p.y < -20 || p.y > H + 20) {
        p.x = Math.random() * W;
        p.y = Math.random() * H;
      }
    }

    requestAnimationFrame(draw);
  }

  // Initial fill
  ctx.fillStyle = '#0a0a0a';
  ctx.fillRect(0, 0, W, H);

  requestAnimationFrame(draw);

  window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'param') {
      switch (e.data.name) {
        case 'SPEED': SPEED = e.data.value; break;
        case 'NOISE_SCALE': NOISE_SCALE = e.data.value; break;
      }
    }
  });
})();
</script>
</body>
</html>
''',
}


def _is_guest(consent: Consent) -> bool:
    return not (consent.memory or consent.mistake_book)


def load_dynamic_background(
    consent: Consent, path: Path | None = None
) -> bool:
    """读取动态背景开关；默认关闭。"""
    if _is_guest(consent):
        return bool(st.session_state.get(DYNAMIC_BACKGROUND_KEY, False))
    try:
        store = SQLiteSettingsStore(path or db_path())
        try:
            values = store.get_all()
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return False
    return bool(values.get(DYNAMIC_BACKGROUND_KEY, False))


def save_dynamic_background(
    consent: Consent, enabled: bool, path: Path | None = None
) -> bool:
    """保存动态背景开关；失败时不阻断主流程。"""
    if _is_guest(consent):
        st.session_state[DYNAMIC_BACKGROUND_KEY] = bool(enabled)
        return True
    try:
        store = SQLiteSettingsStore(path or db_path())
        try:
            store.set_many({DYNAMIC_BACKGROUND_KEY: bool(enabled)})
        finally:
            store.close()
    except (OSError, sqlite3.Error):
        return False
    st.session_state[DYNAMIC_BACKGROUND_KEY] = bool(enabled)
    return True


def shader_html(variant: str = "dashboard") -> str:
    """返回带 reduced-motion 预处理的常量 shader HTML。"""
    html = SHADER_HTML.get(variant, SHADER_HTML["dashboard"])
    if "</head>" in html:
        return html.replace("</head>", _PRELUDE + "</head>", 1)
    return _PRELUDE + html


def render_dynamic_background(
    consent: Consent, variant: str = "dashboard"
) -> None:
    """在仪表盘/空状态渲染动态背景；关闭时不注入 iframe。"""
    if not load_dynamic_background(consent):
        return
    st.components.v1.html(
        shader_html(variant),
        height=180,
        scrolling=False,
    )
