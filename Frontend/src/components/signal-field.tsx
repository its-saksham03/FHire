"use client";

import { useEffect, useRef, useState } from "react";

const VS = `attribute vec2 a_position;
varying vec2 v_texCoord;
void main() {
  v_texCoord = a_position * 0.5 + 0.5;
  gl_Position = vec4(a_position, 0.0, 1.0);
}`;

const FS = `precision highp float;
uniform float u_time;
uniform vec2 u_resolution;
uniform vec2 u_mouse;
varying vec2 v_texCoord;

float hash(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453123);
}

void main() {
    vec2 uv = v_texCoord;
    vec2 center = vec2(0.5, 0.5);
    vec2 target = mix(center, u_mouse / u_resolution, 0.2);

    vec3 baseColor = vec3(0.082, 0.071, 0.169);
    vec3 accentColor = vec3(0.247, 0.878, 0.690);

    vec3 color = baseColor;

    for(float i = 0.0; i < 60.0; i++) {
        float h = hash(vec2(i, 123.45));
        float speed = 0.1 + h * 0.2;
        float phase = h * 6.28;
        vec2 pos = vec2(hash(vec2(i, 1.0)), hash(vec2(i, 2.0)));
        float t = mod(u_time * speed + phase, 10.0) / 10.0;
        vec2 currentPos = mix(pos, target, smoothstep(0.0, 1.0, t));
        float dist = length(uv - currentPos);
        float glow = exp(-dist * 500.0) * (1.0 - t);
        color += accentColor * glow * 0.8;
    }

    float beam = exp(-abs(uv.x - target.x) * 100.0);
    beam *= smoothstep(0.4, 0.6, uv.y);
    color += accentColor * beam * 0.3 * (0.5 + 0.5 * sin(u_time * 2.0));

    gl_FragColor = vec4(color, 1.0);
}`;

interface SignalFieldProps {
  opacity?: number;
  scale?: number;
  rotate?: number;
  className?: string;
}

export function SignalField({ opacity = 0.4, scale = 1, rotate = 0, className = "" }: SignalFieldProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const mouseRef = useRef({ x: 0, y: 0 });
  const timeRef = useRef(0);
  const rafRef = useRef<number>(0);
  const reducedMotion = useRef(false);
  // Determine reduced-motion preference client-side only (avoids hydration mismatch)
  const [prefersReduced, setPrefersReduced] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setPrefersReduced(mq.matches);
    const handler = (e: MediaQueryListEvent) => setPrefersReduced(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  useEffect(() => {
    if (prefersReduced || !mounted) return;

    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl");
    if (!gl) return;

    const compile = (type: number, source: string) => {
      const shader = gl.createShader(type)!;
      gl.shaderSource(shader, source);
      gl.compileShader(shader);
      return shader;
    };

    const program = gl.createProgram()!;
    gl.attachShader(program, compile(gl.VERTEX_SHADER, VS));
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(program);
    gl.useProgram(program);

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]), gl.STATIC_DRAW);

    const posLoc = gl.getAttribLocation(program, "a_position");
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 2, gl.FLOAT, false, 0, 0);

    const uTime = gl.getUniformLocation(program, "u_time");
    const uRes = gl.getUniformLocation(program, "u_resolution");
    const uMouse = gl.getUniformLocation(program, "u_mouse");

    const resize = () => {
      const parent = canvas.parentElement;
      if (!parent) return;
      canvas.width = parent.clientWidth;
      canvas.height = parent.clientHeight;
      gl.viewport(0, 0, canvas.width, canvas.height);
    };

    const ro = new ResizeObserver(resize);
    ro.observe(canvas.parentElement!);
    resize();

    const onMouse = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseRef.current = { x: e.clientX - rect.left, y: rect.height - (e.clientY - rect.top) };
    };
    window.addEventListener("mousemove", onMouse);

    const render = () => {
      timeRef.current += 0.016;
      gl.uniform1f(uTime, timeRef.current);
      gl.uniform2f(uRes, canvas.width, canvas.height);
      gl.uniform2f(uMouse, mouseRef.current.x, mouseRef.current.y);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      rafRef.current = requestAnimationFrame(render);
    };
    render();

    return () => {
      cancelAnimationFrame(rafRef.current);
      ro.disconnect();
      window.removeEventListener("mousemove", onMouse);
    };
  }, [prefersReduced, mounted]);

  // Before mount, render nothing (SSR/hydration safe)
  if (!mounted) {
    return (
      <div
        className={`absolute inset-0 ${className}`}
        style={{ opacity: 0 }}
        aria-hidden
      />
    );
  }

  if (prefersReduced) {
    return (
      <div
        className={`absolute inset-0 bg-primary-container ${className}`}
        style={{ opacity }}
        aria-hidden
      />
    );
  }

  return (
    <canvas
      ref={canvasRef}
      className={`absolute inset-0 h-full w-full pointer-events-none ${className}`}
      style={{ opacity, transform: `scale(${scale}) rotate(${rotate}deg)` }}
      aria-hidden
    />
  );
}
