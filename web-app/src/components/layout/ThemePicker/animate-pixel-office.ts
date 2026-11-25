import { LightingEngine, LiquidGlassRenderer, MathUtils, PixelOfficeScene } from './pixel-office';

export type ColorTheme = 'light' | 'dark';

const transitionDuration = 850;
const frameInterval = 1000 / 120;
const timestampTolerance = 0.5;

export function mountPixelOffice(container: HTMLElement, initialTheme: ColorTheme) {
  const scene = new PixelOfficeScene();
  const lighting = new LightingEngine();
  const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
  const startedAt = performance.now();
  let renderer = createRenderer(false);
  let channels = lighting.getRestingChannels(initialTheme);
  let progress = Number(initialTheme === 'dark');
  let frame: number | null = null;
  let nextFrameAt = 0;
  let inViewport = true;
  let theme = initialTheme;
  let available = true;
  let animation: { start: number; from: number; fromChannels: typeof channels } | undefined;

  function createRenderer(canvas2D: boolean) {
    const next = new LiquidGlassRenderer(document.createElement('canvas'), scene, canvas2D);
    next.canvas.addEventListener('webglcontextlost', useCanvas2D, { once: true });
    next.canvas.setAttribute('data-renderer', next.mode);
    container.replaceChildren(next.canvas);
    resize(next);
    return next;
  }

  function resize(target: LiquidGlassRenderer) {
    const { width, height } = container.getBoundingClientRect();
    target.resize(width, height);
  }

  function useCanvas2D() {
    renderer.dispose();
    try {
      renderer = createRenderer(true);
      requestFrame();
    } catch {
      available = false;
      container.replaceChildren();
      stop();
    }
  }

  function timeline(next: ColorTheme, amount: number) {
    return next === 'dark' ? lighting.evaluateDayToNight(amount) : lighting.evaluateNightToNextDay(amount);
  }

  function settle() {
    animation = undefined;
    progress = Number(theme === 'dark');
    channels = lighting.getRestingChannels(theme);
  }

  function update(now: number) {
    if (!animation) return 0;
    const elapsed = MathUtils.clamp((now - animation.start) / transitionDuration, 0, 1);
    if (elapsed === 1) {
      settle();
      return 0;
    }

    const eased = MathUtils.easeLens(Math.min(1, elapsed / 0.78));
    progress = MathUtils.lerp(animation.from, Number(theme === 'dark'), eased);
    channels = lighting.blendChannels(animation.fromChannels, timeline(theme, elapsed), Math.min(1, elapsed * 5));
    return Math.sin(elapsed * Math.PI);
  }

  function draw(now: number) {
    if (!available) return;
    const activity = update(now);
    const hours = MathUtils.lerp(10.5, 22.5, channels.darkness);
    scene.render(channels, motion.matches ? 0 : (now - startedAt) / 1000, activity, motion.matches, hours);
    renderer.render({ lensProgress: progress, velocity: 0, stretchX: 1, channels });
  }

  function canDraw() {
    return available && inViewport && !document.hidden;
  }

  function requestFrame() {
    if (frame === null && canDraw()) frame = requestAnimationFrame(tick);
  }

  function stop() {
    if (frame !== null) cancelAnimationFrame(frame);
    frame = null;
  }

  function tick(now: number) {
    frame = null;
    if (!canDraw()) return;
    if (motion.matches || now + timestampTolerance >= nextFrameAt) {
      draw(now);
      // Keep the deadline on a 120 Hz timeline without dropping frames for small timestamp variations.
      nextFrameAt = Math.max(now, nextFrameAt + frameInterval);
    }
    if (!motion.matches) requestFrame();
  }

  function refresh() {
    stop();
    nextFrameAt = 0;
    if (motion.matches) settle();
    requestFrame();
  }

  function setTheme(next: ColorTheme) {
    theme = next;
    if (motion.matches) settle();
    else animation = { start: performance.now(), from: progress, fromChannels: channels };
    requestFrame();
  }

  function scrub(next: number) {
    animation = undefined;
    progress = MathUtils.clamp(next, 0, 1);
    channels = theme === 'dark' ? timeline('light', 1 - progress) : timeline('dark', progress);
    requestFrame();
  }

  const sizeObserver = new ResizeObserver(() => {
    resize(renderer);
    requestFrame();
  });
  sizeObserver.observe(container);
  const visibilityObserver = new IntersectionObserver(([entry]) => {
    inViewport = entry.isIntersecting;
    refresh();
  });
  visibilityObserver.observe(container);
  document.addEventListener('visibilitychange', refresh);
  motion.addEventListener('change', refresh);
  refresh();

  function dispose() {
    available = false;
    stop();
    sizeObserver.disconnect();
    visibilityObserver.disconnect();
    document.removeEventListener('visibilitychange', refresh);
    motion.removeEventListener('change', refresh);
    renderer.canvas.removeEventListener('webglcontextlost', useCanvas2D);
    renderer.dispose();
    container.replaceChildren();
  }

  return { setTheme, scrub, dispose };
}
