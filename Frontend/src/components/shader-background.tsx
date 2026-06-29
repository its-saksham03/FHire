"use client";

import { useEffect, useRef } from "react";

export function ShaderBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    let gl: WebGLRenderingContext | null = null;
    let animationFrameId: number;

    // WebGL implementation
    try {
      gl = (canvas.getContext("webgl") ||
        canvas.getContext("experimental-webgl")) as WebGLRenderingContext | null;
    } catch (e) {
      console.warn("WebGL not supported, falling back to 2D Canvas animation", e);
    }

    if (gl) {
      const vs = `
        attribute vec2 a_position;
        varying vec2 v_texCoord;
        void main() {
          v_texCoord = a_position * 0.5 + 0.5;
          gl_Position = vec4(a_position, 0.0, 1.0);
        }
      `;

      const fs = `
        precision highp float;
        uniform float u_time;
        uniform vec2 u_resolution;
        uniform vec2 u_mouse;
        varying vec2 v_texCoord;

        float hash(vec2 p) {
            p = fract(p * vec2(123.34, 456.21));
            p += dot(p, p + 45.32);
            return fract(p.x * p.y);
        }

        float noise(vec2 p) {
            vec2 i = floor(p);
            vec2 f = fract(p);
            f = f * f * (3.0 - 2.0 * f);
            float a = hash(i);
            float b = hash(i + vec2(1.0, 0.0));
            float c = hash(i + vec2(0.0, 1.0));
            float d = hash(i + vec2(1.0, 1.0));
            return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
        }

        void main() {
            vec2 uv = v_texCoord;
            vec2 mouse = u_mouse / u_resolution;
            
            // Deep Space Base
            vec3 color = vec3(0.047, 0.055, 0.071); // #0c0e12 equivalent
            
            // Flowing ice blue layers
            float n1 = noise(uv * 2.5 + u_time * 0.03);
            float n2 = noise(uv * 5.0 - u_time * 0.05);
            float flow = smoothstep(0.35, 0.65, n1 * n2);
            
            vec3 iceBlue = vec3(0.49, 0.83, 0.99); // #7dd3fc
            color = mix(color, iceBlue, flow * 0.07);
            
            // Grid lattice lines
            vec2 grid = fract(uv * 40.0);
            float line = smoothstep(0.0, 0.02, grid.x) * smoothstep(0.0, 0.02, grid.y);
            color += (1.0 - line) * 0.015;
            
            // Signal particles
            vec2 p_uv = uv * 20.0;
            vec2 ip = floor(p_uv);
            vec2 fp = fract(p_uv);
            float n = hash(ip);
            if (n > 0.975) {
                float t = u_time * 0.4 + n * 10.0;
                vec2 offset = vec2(sin(t), cos(t)) * 0.25;
                float spark = smoothstep(0.25, 0.0, length(fp - 0.5 + offset));
                color += iceBlue * spark * (0.2 + 0.6 * sin(u_time + n * 5.0));
            }
            
            // Mouse glow
            float m_glow = smoothstep(0.35, 0.0, length(uv - mouse));
            color += iceBlue * m_glow * 0.035;

            gl_FragColor = vec4(color, 1.0);
        }
      `;

      const createShader = (type: number, source: string) => {
        const s = gl!.createShader(type);
        if (!s) return null;
        gl!.shaderSource(s, source);
        gl!.compileShader(s);
        if (!gl!.getShaderParameter(s, gl!.COMPILE_STATUS)) {
          console.error("Shader compile error:", gl!.getShaderInfoLog(s));
          gl!.deleteShader(s);
          return null;
        }
        return s;
      };

      const vsShader = createShader(gl.VERTEX_SHADER, vs);
      const fsShader = createShader(gl.FRAGMENT_SHADER, fs);
      const prog = gl.createProgram();

      if (vsShader && fsShader && prog) {
        gl.attachShader(prog, vsShader);
        gl.attachShader(prog, fsShader);
        gl.linkProgram(prog);
        gl.useProgram(prog);

        const buf = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, buf);
        gl.bufferData(
          gl.ARRAY_BUFFER,
          new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]),
          gl.STATIC_DRAW
        );

        const pos = gl.getAttribLocation(prog, "a_position");
        gl.enableVertexAttribArray(pos);
        gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0);

        const uTime = gl.getUniformLocation(prog, "u_time");
        const uRes = gl.getUniformLocation(prog, "u_resolution");
        const uMouse = gl.getUniformLocation(prog, "u_mouse");

        let mouseX = canvas.width / 2;
        let mouseY = canvas.height / 2;

        const handleMouseMove = (e: MouseEvent) => {
          const rect = canvas.getBoundingClientRect();
          if (rect.width && rect.height) {
            const nx = (e.clientX - rect.left) / rect.width;
            const ny = 1.0 - (e.clientY - rect.top) / rect.height;
            mouseX = nx * canvas.width;
            mouseY = ny * canvas.height;
          }
        };

        window.addEventListener("mousemove", handleMouseMove);

        const syncSize = () => {
          if (!canvas) return;
          const w = window.innerWidth;
          const h = window.innerHeight;
          if (canvas.width !== w || canvas.height !== h) {
            canvas.width = w;
            canvas.height = h;
          }
        };

        window.addEventListener("resize", syncSize);
        syncSize();

        const render = (t: number) => {
          if (!canvas || !gl) return;
          gl.viewport(0, 0, canvas.width, canvas.height);
          if (uTime) gl.uniform1f(uTime, t * 0.001);
          if (uRes) gl.uniform2f(uRes, canvas.width, canvas.height);
          if (uMouse) gl.uniform2f(uMouse, mouseX, mouseY);
          gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
          animationFrameId = requestAnimationFrame(render);
        };

        render(0);

        return () => {
          window.removeEventListener("mousemove", handleMouseMove);
          window.removeEventListener("resize", syncSize);
          cancelAnimationFrame(animationFrameId);
        };
      }
    }

    // 2D Canvas Fallback (CPU friendly, matches colors and vibes perfectly)
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let width = (canvas.width = window.innerWidth);
    let height = (canvas.height = window.innerHeight);

    const handleResize = () => {
      width = canvas.width = window.innerWidth;
      height = canvas.height = window.innerHeight;
    };
    window.addEventListener("resize", handleResize);

    interface Particle {
      x: number;
      y: number;
      size: number;
      speed: number;
      opacity: number;
      angle: number;
    }

    const particles: Particle[] = Array.from({ length: 40 }, () => ({
      x: Math.random() * width,
      y: Math.random() * height,
      size: 1 + Math.random() * 2,
      speed: 0.1 + Math.random() * 0.3,
      opacity: 0.1 + Math.random() * 0.5,
      angle: Math.random() * Math.PI * 2,
    }));

    const render2d = (t: number) => {
      ctx.fillStyle = "#0c0e12";
      ctx.fillRect(0, 0, width, height);

      // Render flowing gradient background
      const grad = ctx.createRadialGradient(
        width / 2 + Math.sin(t * 0.0005) * (width * 0.2),
        height / 2 + Math.cos(t * 0.0003) * (height * 0.2),
        10,
        width / 2,
        height / 2,
        Math.max(width, height) * 0.8
      );
      grad.addColorStop(0, "rgba(125, 211, 252, 0.04)"); // transparent ice blue
      grad.addColorStop(1, "rgba(12, 14, 18, 0)");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, width, height);

      // Render Crystalline Lattice Grid
      ctx.strokeStyle = "rgba(148, 163, 184, 0.015)";
      ctx.lineWidth = 1;
      const gridSize = 60;
      ctx.beginPath();
      for (let x = 0; x < width; x += gridSize) {
        ctx.moveTo(x, 0);
        ctx.lineTo(x, height);
      }
      for (let y = 0; y < height; y += gridSize) {
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
      }
      ctx.stroke();

      // Render flowing particles
      ctx.fillStyle = "rgba(125, 211, 252, 0.5)";
      particles.forEach((p) => {
        p.x += Math.cos(p.angle) * p.speed;
        p.y += Math.sin(p.angle) * p.speed;
        p.angle += (Math.random() - 0.5) * 0.02;

        if (p.x < 0) p.x = width;
        if (p.x > width) p.x = 0;
        if (p.y < 0) p.y = height;
        if (p.y > height) p.y = 0;

        ctx.globalAlpha = p.opacity * (0.3 + 0.7 * Math.abs(Math.sin(t * 0.001 + p.x)));
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
        ctx.fill();
      });
      ctx.globalAlpha = 1.0;

      animationFrameId = requestAnimationFrame(render2d);
    };

    render2d(0);

    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      className="fixed inset-0 -z-10 h-full w-full pointer-events-none opacity-60"
      style={{ display: "block" }}
    />
  );
}
