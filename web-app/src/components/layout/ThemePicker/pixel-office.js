/* Adapted from https://github.com/diepvantien/pixel-liquid-glass-toggle.
 *
 * MIT License
 *
 * Copyright (c) 2026 Diep Van Tien
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 */

const MathUtils = {
  clamp(v, min, max) {
    return v < min ? min : (v > max ? max : v);
  },
  lerp(a, b, t) {
    return a + (b - a) * t;
  },
  smoothstep(edge0, edge1, x) {
    const t = MathUtils.clamp((x - edge0) / (edge1 - edge0), 0, 1);
    return t * t * (3 - 2 * t);
  },
  bell(t, center, width) {
    const d = (t - center) / width;
    return Math.exp(-d * d * 2.6);
  },
  easeLens(t) {
    t = MathUtils.clamp(t, 0, 1);
    if (t === 0 || t === 1) return t;
    const c4 = (2 * Math.PI) / 3.4;
    const cubic = t < 0.5
      ? 4 * t * t * t
      : 1 - Math.pow(-2 * t + 2, 3) / 2;
    const settle = Math.pow(2, -8 * t) * Math.sin((t * 6.5 - 0.75) * c4) * 0.032;
    return MathUtils.clamp(cubic + (t > 0.65 ? settle * (1 - t) * 2.8 : 0), 0, 1.022);
  },
  lerpRGB(c1, c2, t) {
    t = MathUtils.clamp(t, 0, 1);
    return [
      Math.round(c1[0] + (c2[0] - c1[0]) * t),
      Math.round(c1[1] + (c2[1] - c1[1]) * t),
      Math.round(c1[2] + (c2[2] - c1[2]) * t)
    ];
  },
  rgbStr(rgb, a = 1) {
    if (a >= 0.999) return `rgb(${rgb[0]},${rgb[1]},${rgb[2]})`;
    return `rgba(${rgb[0]},${rgb[1]},${rgb[2]},${a.toFixed(3)})`;
  }
};

class LightingEngine {
  constructor() {
    this.channels = this.getRestingChannels('light');
  }

  getRestingChannels(mode) {
    if (mode === 'dark') {
      return {
        ambientDaylight: 0.08,
        sunsetWarmth: 0.00,
        sunriseWarmth: 0.00,
        nightAmbient: 0.45,
        cityWindowEmission: 0.85,
        monitorEmission: 0.80,
        deskLampEmission: 1.00,
        glassReflectionIntensity: 0.35,
        frameReflectionIntensity: 0.25,
        darkness: 1.00
      };
    }
    return {
      ambientDaylight: 1.00,
      sunsetWarmth: 0.00,
      sunriseWarmth: 0.00,
      nightAmbient: 0.00,
      cityWindowEmission: 0.05,
      monitorEmission: 0.15,
      deskLampEmission: 0.00,
      glassReflectionIntensity: 0.90,
      frameReflectionIntensity: 0.85,
      darkness: 0.00
    };
  }

  evaluateDayToNight(p) {
    p = MathUtils.clamp(p, 0, 1);
    const dayDrop = MathUtils.smoothstep(0.18, 0.82, p);
    const sunset = MathUtils.bell(p, 0.44, 0.25);
    const nightRise = MathUtils.smoothstep(0.38, 0.92, p);
    const cityLights = MathUtils.smoothstep(0.45, 0.94, p);
    const monitorRise = MathUtils.smoothstep(0.18, 0.72, p);
    const lampRise = MathUtils.smoothstep(0.46, 0.88, p);
    const reflectDrop = MathUtils.smoothstep(0.22, 0.86, p);

    return {
      ambientDaylight: MathUtils.lerp(1.00, 0.08, dayDrop),
      sunsetWarmth: MathUtils.clamp(sunset * 1.05, 0, 1),
      sunriseWarmth: 0.0,
      nightAmbient: MathUtils.lerp(0.00, 0.45, nightRise),
      cityWindowEmission: MathUtils.lerp(0.05, 0.85, cityLights),
      monitorEmission: MathUtils.lerp(0.15, 0.80, monitorRise),
      deskLampEmission: MathUtils.lerp(0.00, 1.00, lampRise),
      glassReflectionIntensity: MathUtils.lerp(0.90, 0.35, reflectDrop),
      frameReflectionIntensity: MathUtils.lerp(0.85, 0.25, reflectDrop),
      darkness: MathUtils.smoothstep(0.28, 0.88, p)
    };
  }

  evaluateNightToNextDay(p) {
    p = MathUtils.clamp(p, 0, 1);
    const preDawnLift = MathUtils.smoothstep(0.08, 0.76, p);
    const sunrise = MathUtils.bell(p, 0.46, 0.23);
    const nightFade = MathUtils.smoothstep(0.16, 0.78, p);
    const cityFade = MathUtils.smoothstep(0.30, 0.84, p);
    const monitorFade = MathUtils.smoothstep(0.28, 0.82, p);
    const lampFade = MathUtils.smoothstep(0.32, 0.74, p);
    const reflectRise = MathUtils.smoothstep(0.18, 0.84, p);

    return {
      ambientDaylight: MathUtils.lerp(0.08, 1.00, preDawnLift),
      sunsetWarmth: 0.0,
      sunriseWarmth: MathUtils.clamp(sunrise * 0.95, 0, 1),
      nightAmbient: MathUtils.lerp(0.45, 0.00, nightFade),
      cityWindowEmission: MathUtils.lerp(0.85, 0.05, cityFade),
      monitorEmission: MathUtils.lerp(0.80, 0.15, monitorFade),
      deskLampEmission: MathUtils.lerp(1.00, 0.00, lampFade),
      glassReflectionIntensity: MathUtils.lerp(0.35, 0.90, reflectRise),
      frameReflectionIntensity: MathUtils.lerp(0.25, 0.85, reflectRise),
      darkness: 1.0 - MathUtils.smoothstep(0.14, 0.76, p)
    };
  }

  /**
   * @template {Record<string, number>} Channels
   * @param {Channels} fromCh
   * @param {Channels} toCh
   * @param {number} t
   * @returns {Channels}
   */
  blendChannels(fromCh, toCh, t) {
    const out = {};
    for (const key in toCh) {
      out[key] = MathUtils.lerp(fromCh[key] ?? 0, toCh[key], t);
    }
    return out;
  }

  formatLogicalClock(timeline, progress) {
    let hours = 10.5;
    if (timeline === 'idle_day') hours = 10.5;
    else if (timeline === 'idle_night') hours = 22.5;
    else if (timeline === 'day_to_night') hours = MathUtils.lerp(14.5, 22.5, progress);
    else if (timeline === 'night_to_next_day') hours = MathUtils.lerp(3.5, 9.5, progress);
    const h = Math.floor(hours) % 24;
    const m = Math.floor((hours - Math.floor(hours)) * 60);
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  }
}

class PixelOfficeScene {
  constructor() {
    this.width = 222;
    this.height = 120;

    this.canvas = document.createElement('canvas');
    this.canvas.width = this.width;
    this.canvas.height = this.height;
    this.ctx = this.canvas.getContext('2d', { alpha: false });
    this.ctx.imageSmoothingEnabled = false;

    this.cityBuildings = this._createCityLayout();
    this.stars = this._createStars();
    this.clouds = [
      { x: 6, y: 14, w: 15, speed: 0.9 },
      { x: 36, y: 22, w: 12, speed: 0.65 },
      { x: 52, y: 10, w: 10, speed: 1.15 }
    ];
    this.dustMotes = [
      { bx: 132, by: 62, phase: 0.2, speed: 0.8 },
      { bx: 142, by: 56, phase: 1.9, speed: 0.6 },
      { bx: 126, by: 68, phase: 3.4, speed: 0.7 },
      { bx: 138, by: 66, phase: 4.8, speed: 0.5 }
    ];
  }

  _createStars() {
    const stars = [];
    let seed = 9137;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };
    for (let i = 0; i < 22; i++) {
      stars.push({
        x: Math.floor(2 + rand() * 64),
        y: Math.floor(6 + rand() * 26),
        phase: rand() * Math.PI * 2,
        speed: 1.2 + rand() * 2.4
      });
    }
    return stars;
  }

  _createCityLayout() {
    const buildings = [
      { x: 2,  y: 26, w: 13, h: 64, depth: 0, antenna: true,  dayCol: [152, 182, 214], nightCol: [20, 32, 62] },
      { x: 16, y: 16, w: 15, h: 74, depth: 0, antenna: true,  dayCol: [140, 172, 208], nightCol: [18, 29, 56] },
      { x: 32, y: 24, w: 14, h: 66, depth: 0, antenna: false, dayCol: [156, 185, 216], nightCol: [22, 35, 66] },
      { x: 48, y: 19, w: 16, h: 71, depth: 0, antenna: true,  dayCol: [144, 176, 210], nightCol: [19, 31, 59] },
      { x: 0,  y: 38, w: 15, h: 52, depth: 1, antenna: false, dayCol: [118, 150, 186], nightCol: [15, 24, 48] },
      { x: 18, y: 31, w: 17, h: 59, depth: 1, antenna: false, dayCol: [108, 140, 178], nightCol: [14, 22, 44] },
      { x: 38, y: 36, w: 19, h: 54, depth: 1, antenna: false, dayCol: [122, 154, 190], nightCol: [16, 26, 51] },
      { x: 58, y: 42, w: 10, h: 48, depth: 1, antenna: false, dayCol: [114, 146, 182], nightCol: [15, 24, 46] }
    ];

    let seed = 4219;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };

    for (const b of buildings) {
      b.windows = [];
      for (let wy = b.y + 4; wy < 86; wy += 5) {
        for (let wx = b.x + 2; wx < b.x + b.w - 3; wx += 4) {
          const r = rand();
          if (r < 0.66) {
            const warmPick = rand();
            const color = warmPick < 0.56
              ? [255, 224, 130]
              : (warmPick < 0.84 ? [248, 174, 84] : [138, 208, 255]);
            b.windows.push({
              x: wx,
              y: wy,
              threshold: 0.10 + rand() * 0.72,
              intensity: 0.62 + rand() * 0.38,
              color
            });
          }
        }
      }
    }
    return buildings;
  }

  _litColor(dayRGB, nightRGB, ch, warmWeight = 0.25) {
    const t = MathUtils.clamp(ch.darkness, 0, 1);
    let c = MathUtils.lerpRGB(dayRGB, nightRGB, t);
    if (ch.sunsetWarmth > 0.01) {
      c = MathUtils.lerpRGB(c, [242, 150, 82], ch.sunsetWarmth * warmWeight);
    }
    if (ch.sunriseWarmth > 0.01) {
      c = MathUtils.lerpRGB(c, [246, 178, 152], ch.sunriseWarmth * warmWeight);
    }
    return c;
  }

  px(x, y, w, h, rgb, a = 1) {
    this.ctx.fillStyle = MathUtils.rgbStr(rgb, a);
    this.ctx.fillRect(Math.round(x), Math.round(y), Math.round(w), Math.round(h));
  }

  render(ch, animTime, transitionActivity, reducedMotion, logicalHours = 10.5) {
    this.ctx.imageSmoothingEnabled = false;
    this._drawRoomShell(ch);
    this._drawCityWindow(ch, animTime, reducedMotion);
    this._drawTiledFloor(ch);
    this._drawWallDecorations(ch, logicalHours);
    this._drawRightStorage(ch, animTime, reducedMotion);
    this._drawWorkstationAndWorker(ch, animTime, transitionActivity, reducedMotion);
    this._drawLocalLightSources(ch, animTime, reducedMotion);
  }

  _drawRoomShell(ch) {
    const ceilCol = this._litColor([214, 221, 234], [15, 23, 45], ch, 0.14);
    this.px(0, 0, 222, 11, ceilCol);
    this.px(0, 10, 222, 1, this._litColor([194, 203, 219], [11, 18, 36], ch, 0.12));

    const wallCol = this._litColor([242, 244, 249], [25, 38, 69], ch, 0.22);
    const wallSeam = this._litColor([231, 235, 244], [21, 32, 59], ch, 0.16);
    this.px(68, 11, 154, 79, wallCol);
    this.px(110, 11, 1, 79, wallSeam);
    this.px(158, 11, 1, 79, wallSeam);

    this.px(68, 86, 154, 4, this._litColor([204, 211, 224], [17, 27, 50], ch, 0.16));
    this.px(68, 86, 154, 1, this._litColor([224, 229, 238], [26, 39, 70], ch, 0.14));

    const pillarCol = this._litColor([208, 216, 230], [21, 33, 60], ch, 0.20);
    this.px(66, 9, 5, 83, pillarCol);
    this.px(70, 9, 1, 83, this._litColor([180, 191, 210], [14, 22, 42], ch, 0.12));

    const lightFixture = this._litColor([252, 254, 255], [30, 44, 76], ch, 0.10);
    this.px(98, 4, 44, 3, lightFixture);
    this.px(100, 7, 40, 1, this._litColor([236, 242, 252], [22, 34, 62], ch, 0.10));
  }

  _drawCityWindow(ch, animTime, reducedMotion) {
    const skyTopDay = [146, 198, 244];
    const skyBotDay = [210, 234, 252];
    const skyTopNight = [10, 17, 40];
    const skyBotNight = [22, 36, 72];

    let topCol = MathUtils.lerpRGB(skyTopDay, skyTopNight, ch.darkness);
    let botCol = MathUtils.lerpRGB(skyBotDay, skyBotNight, ch.darkness);

    if (ch.sunsetWarmth > 0.01) {
      topCol = MathUtils.lerpRGB(topCol, [116, 98, 166], ch.sunsetWarmth * 0.68);
      botCol = MathUtils.lerpRGB(botCol, [254, 152, 74], ch.sunsetWarmth * 0.94);
    }
    if (ch.sunriseWarmth > 0.01) {
      topCol = MathUtils.lerpRGB(topCol, [112, 148, 210], ch.sunriseWarmth * 0.58);
      botCol = MathUtils.lerpRGB(botCol, [255, 190, 156], ch.sunriseWarmth * 0.90);
    }

    for (let y = 6; y < 90; y += 2) {
      const gy = (y - 6) / 84;
      this.px(0, y, 66, 2, MathUtils.lerpRGB(topCol, botCol, gy));
    }

    if (ch.darkness > 0.45) {
      const starVis = MathUtils.smoothstep(0.45, 0.85, ch.darkness);
      for (const st of this.stars) {
        const tw = reducedMotion ? 0.8 : (0.45 + 0.55 * Math.sin(animTime * st.speed + st.phase));
        this.px(st.x, st.y, 1, 1, [224, 236, 255], starVis * tw * 0.85);
      }
    }

    if (ch.ambientDaylight > 0.12 || ch.sunsetWarmth > 0.1 || ch.sunriseWarmth > 0.1) {
      let cloudCol = [248, 252, 255];
      if (ch.sunsetWarmth > 0.05) cloudCol = MathUtils.lerpRGB(cloudCol, [255, 198, 138], ch.sunsetWarmth * 0.85);
      if (ch.sunriseWarmth > 0.05) cloudCol = MathUtils.lerpRGB(cloudCol, [255, 214, 200], ch.sunriseWarmth * 0.85);
      const cAlpha = MathUtils.clamp(ch.ambientDaylight * 0.72 + (ch.sunsetWarmth + ch.sunriseWarmth) * 0.45, 0, 0.8);

      for (const cl of this.clouds) {
        const cx = reducedMotion ? cl.x : ((cl.x + animTime * cl.speed) % 82) - 16;
        this.px(cx, cl.y, cl.w, 3, cloudCol, cAlpha);
        this.px(cx + 3, cl.y - 2, cl.w - 6, 2, cloudCol, cAlpha * 0.9);
      }
    }

    this.px(0, 72, 66, 18, MathUtils.lerpRGB(botCol, [255, 255, 255], 0.16 * ch.ambientDaylight), 0.32);

    for (const b of this.cityBuildings) {
      let bCol = MathUtils.lerpRGB(b.dayCol, b.nightCol, ch.darkness);
      if (ch.sunsetWarmth > 0.01) {
        bCol = MathUtils.lerpRGB(bCol, [154, 96, 84], ch.sunsetWarmth * (b.depth === 0 ? 0.56 : 0.36));
      }
      if (ch.sunriseWarmth > 0.01) {
        bCol = MathUtils.lerpRGB(bCol, [152, 124, 152], ch.sunriseWarmth * (b.depth === 0 ? 0.52 : 0.32));
      }
      this.px(b.x, b.y, b.w, b.h, bCol);

      if (b.antenna) {
        this.px(b.x + Math.floor(b.w / 2), b.y - 5, 1, 5, bCol);
        if (ch.cityWindowEmission > 0.25) {
          const blink = reducedMotion ? 0.85 : (0.45 + 0.55 * Math.sin(animTime * 2.8 + b.x));
          this.px(b.x + Math.floor(b.w / 2), b.y - 6, 1, 1, [255, 84, 98], ch.cityWindowEmission * blink);
        }
      }
      this.px(b.x + 2, b.y - 2, 4, 2, bCol);

      const edgeCol = MathUtils.lerpRGB([214, 234, 252], [40, 60, 102], ch.darkness);
      this.px(b.x + b.w - 1, b.y, 1, b.h, edgeCol, 0.65);

      const darkWin = MathUtils.lerpRGB([164, 198, 228], [10, 16, 34], ch.darkness);
      for (let wy = b.y + 4; wy < 86; wy += 5) {
        for (let wx = b.x + 2; wx < b.x + b.w - 3; wx += 4) {
          this.px(wx, wy, 2, 3, darkWin, 0.72);
        }
      }

      if (ch.cityWindowEmission > 0.05) {
        for (const w of b.windows) {
          const alpha = MathUtils.smoothstep(
            w.threshold - 0.12,
            w.threshold + 0.16,
            ch.cityWindowEmission
          ) * w.intensity;
          if (alpha > 0.04) {
            this.px(w.x, w.y, 2, 3, w.color, alpha);
          }
        }
      }
    }

    if (ch.cityWindowEmission > 0.3 && !reducedMotion) {
      const tAlpha = MathUtils.smoothstep(0.3, 0.75, ch.cityWindowEmission) * 0.85;
      const car1X = (animTime * 9.5) % 66;
      const car2X = 66 - ((animTime * 7.2 + 22) % 66);
      const car3X = (animTime * 11.0 + 38) % 66;
      this.px(car1X, 85, 2, 1, [255, 236, 178], tAlpha);
      this.px(car2X, 86, 2, 1, [255, 92, 92], tAlpha);
      this.px(car3X, 85, 2, 1, [255, 242, 196], tAlpha * 0.8);
    }

    const glassSheenAlpha = 0.07 + ch.ambientDaylight * 0.15;
    const sheenCol = ch.sunsetWarmth > 0.2
      ? [255, 224, 180]
      : (ch.sunriseWarmth > 0.2 ? [255, 220, 210] : [224, 244, 255]);
    for (let i = 0; i < 32; i++) {
      this.px(8 + i, 14 + Math.floor(i * 1.45), 4, 2, sheenCol, glassSheenAlpha);
    }
    for (let i = 0; i < 20; i++) {
      this.px(36 + i, 10 + Math.floor(i * 1.35), 2, 2, sheenCol, glassSheenAlpha * 0.75);
    }

    this.px(0, 6, 66, 3, this._litColor([184, 196, 214], [24, 34, 62], ch, 0.15));

    const frameMain = this._litColor([84, 106, 136], [16, 24, 46], ch, 0.18);
    const frameHi = this._litColor([140, 162, 190], [34, 48, 80], ch, 0.18);

    this.px(22, 6, 3, 84, frameMain);
    this.px(24, 6, 1, 84, frameHi, 0.5);
    this.px(45, 6, 3, 84, frameMain);
    this.px(47, 6, 1, 84, frameHi, 0.5);
    this.px(63, 6, 3, 84, frameMain);

    this.px(0, 39, 66, 2, frameMain);
    this.px(0, 88, 68, 4, frameMain);
    this.px(0, 88, 68, 1, frameHi, 0.75);
  }

  _drawTiledFloor(ch) {
    const tileLight = this._litColor([154, 170, 194], [23, 35, 64], ch, 0.22);
    const tileDark  = this._litColor([134, 151, 176], [18, 28, 52], ch, 0.22);
    const groutCol  = this._litColor([114, 131, 156], [13, 21, 40], ch, 0.15);

    this.px(0, 90, 222, 30, tileLight);

    const rowHeights = [5, 6, 7, 6, 6];
    let cy = 90;
    for (let r = 0; r < rowHeights.length; r++) {
      const rh = rowHeights[r];
      const tileW = 20 + r * 4;
      const offset = (r % 2) * Math.floor(tileW / 2);
      for (let tx = -tileW; tx < 236; tx += tileW) {
        const idx = Math.floor((tx + tileW * 5) / tileW);
        const isAlt = (idx + r) % 2 === 0;
        this.px(tx + offset, cy, tileW, rh, isAlt ? tileLight : tileDark);
        this.px(tx + offset, cy, 1, rh, groutCol, 0.52);
      }
      this.px(0, cy, 222, 1, groutCol, 0.68);
      cy += rh;
    }

    if (ch.ambientDaylight > 0.14 || ch.sunsetWarmth > 0.08 || ch.sunriseWarmth > 0.08) {
      let shaftCol = [218, 238, 255];
      if (ch.sunsetWarmth > 0.08) shaftCol = MathUtils.lerpRGB(shaftCol, [255, 186, 108], ch.sunsetWarmth);
      if (ch.sunriseWarmth > 0.08) shaftCol = MathUtils.lerpRGB(shaftCol, [255, 208, 184], ch.sunriseWarmth);
      const alpha = 0.19 * ch.ambientDaylight + 0.18 * (ch.sunsetWarmth + ch.sunriseWarmth);
      for (let i = 0; i < 24; i++) {
        this.px(6 + Math.floor(i * 0.7), 91 + i, 52, 1, shaftCol, alpha * (1 - i / 36));
      }
    }
  }

  _drawWallDecorations(ch, logicalHours) {
    const clockRim = this._litColor([92, 108, 134], [24, 36, 66], ch, 0.15);
    const clockFace = this._litColor([252, 253, 255], [40, 56, 94], ch, 0.18);
    const clockHand = this._litColor([46, 58, 82], [182, 206, 248], ch, 0.1);
    this.px(76, 16, 9, 11, clockRim);
    this.px(75, 17, 11, 9, clockRim);
    this.px(77, 17, 7, 9, clockFace);
    this.px(76, 18, 9, 7, clockFace);
    const cx = 80, cy = 21;
    const hAngle = ((logicalHours % 12) / 12) * Math.PI * 2 - Math.PI / 2;
    const mAngle = ((logicalHours % 1)) * Math.PI * 2 - Math.PI / 2;
    this.px(cx, cy, 1, 1, clockHand);
    this.px(cx + Math.round(Math.cos(hAngle) * 2), cy + Math.round(Math.sin(hAngle) * 2), 1, 1, clockHand);
    this.px(cx + Math.round(Math.cos(mAngle) * 3), cy + Math.round(Math.sin(mAngle) * 3), 1, 1, [226, 98, 98]);

    const frameCol = this._litColor([88, 104, 130], [20, 30, 56], ch, 0.15);
    const canvasCol = this._litColor([252, 253, 255], [32, 46, 80], ch, 0.18);
    this.px(91, 18, 32, 21, frameCol);
    this.px(92, 19, 30, 19, canvasCol);

    const gridCol = this._litColor([228, 234, 244], [44, 60, 96], ch, 0.1);
    this.px(94, 24, 26, 1, gridCol);
    this.px(94, 29, 26, 1, gridCol);
    this.px(94, 34, 26, 1, gridCol);

    this.px(95, 32, 3, 4, this._litColor([98, 156, 228], [52, 92, 154], ch, 0.1));
    this.px(100, 29, 3, 7, this._litColor([98, 156, 228], [52, 92, 154], ch, 0.1));
    this.px(105, 27, 3, 9, this._litColor([84, 188, 168], [46, 118, 118], ch, 0.1));
    this.px(110, 25, 3, 11, this._litColor([244, 178, 88], [164, 116, 62], ch, 0.2));
    this.px(115, 22, 3, 14, this._litColor([236, 118, 106], [156, 78, 84], ch, 0.2));

    const lineCol = this._litColor([54, 102, 178], [122, 178, 252], ch, 0.1);
    this.px(95, 31, 4, 1, lineCol);
    this.px(99, 28, 5, 1, lineCol);
    this.px(104, 26, 5, 1, lineCol);
    this.px(109, 24, 5, 1, lineCol);
    this.px(114, 21, 5, 1, lineCol);

    const boardBorder = this._litColor([164, 174, 192], [28, 40, 68], ch, 0.18);
    const boardBg = this._litColor([224, 228, 238], [36, 50, 82], ch, 0.18);
    this.px(128, 20, 28, 22, boardBorder);
    this.px(129, 21, 26, 20, boardBg);

    this.px(131, 23, 6, 6, this._litColor([252, 226, 118], [148, 128, 68], ch, 0.2));
    this.px(139, 22, 6, 6, this._litColor([250, 154, 156], [142, 76, 94], ch, 0.2));
    this.px(147, 24, 6, 6, this._litColor([136, 212, 244], [64, 114, 154], ch, 0.15));
    this.px(132, 32, 6, 6, this._litColor([154, 224, 168], [68, 124, 96], ch, 0.15));
    this.px(141, 31, 7, 7, this._litColor([255, 194, 112], [156, 112, 66], ch, 0.2));

    const inkCol = this._litColor([124, 118, 112], [58, 56, 68], ch, 0.1);
    this.px(132, 25, 4, 1, inkCol, 0.45);
    this.px(140, 24, 4, 1, inkCol, 0.45);
    this.px(142, 34, 5, 1, inkCol, 0.45);
  }

  _drawRightStorage(ch, animTime, reducedMotion) {
    const cabMain  = this._litColor([232, 236, 244], [32, 46, 78], ch, 0.20);
    const cabSide  = this._litColor([198, 206, 222], [24, 36, 64], ch, 0.18);
    const cabShelf = this._litColor([176, 186, 204], [19, 30, 54], ch, 0.16);
    const cabBack  = this._litColor([194, 204, 220], [20, 31, 58], ch, 0.16);

    this.px(162, 93, 46, 4, [12, 20, 40], 0.36 + ch.darkness * 0.28);

    this.px(164, 26, 42, 68, cabMain);
    this.px(164, 26, 3, 68, cabSide);
    this.px(203, 26, 3, 68, cabSide);
    this.px(164, 26, 42, 3, cabSide);

    this.px(167, 29, 36, 14, cabBack);
    this.px(167, 45, 36, 14, cabBack);
    this.px(167, 61, 36, 14, cabBack);

    this.px(167, 43, 36, 2, cabShelf);
    this.px(167, 59, 36, 2, cabShelf);
    this.px(167, 75, 36, 2, cabShelf);

    this.px(167, 77, 17, 15, this._litColor([218, 224, 236], [28, 41, 70], ch, 0.18));
    this.px(186, 77, 17, 15, this._litColor([218, 224, 236], [28, 41, 70], ch, 0.18));
    this.px(184, 77, 2, 15, cabShelf);
    this.px(181, 82, 1, 5, cabShelf);
    this.px(188, 82, 1, 5, cabShelf);

    this.px(169, 32, 4, 11, this._litColor([82, 134, 204], [42, 74, 128], ch, 0.12));
    this.px(173, 34, 3, 9, this._litColor([232, 108, 102], [132, 58, 66], ch, 0.18));
    this.px(176, 31, 4, 12, this._litColor([94, 178, 152], [44, 98, 96], ch, 0.12));
    this.px(180, 35, 3, 8, this._litColor([244, 196, 92], [142, 108, 56], ch, 0.18));
    this.px(184, 35, 3, 8, this._litColor([154, 124, 212], [72, 58, 124], ch, 0.14));
    this.px(191, 33, 10, 10, this._litColor([118, 138, 168], [38, 54, 88], ch, 0.14));
    this.px(194, 36, 4, 2, cabMain);

    this.px(169, 49, 15, 10, this._litColor([238, 132, 62], [148, 76, 44], ch, 0.25));
    this.px(169, 49, 15, 3, this._litColor([252, 164, 92], [176, 98, 56], ch, 0.25));
    this.px(174, 54, 5, 2, this._litColor([255, 232, 198], [218, 164, 118], ch, 0.2));

    this.px(187, 50, 14, 9, this._litColor([124, 138, 160], [34, 48, 78], ch, 0.15));
    this.px(189, 51, 10, 3, this._litColor([178, 192, 214], [52, 70, 108], ch, 0.15));
    this.px(190, 56, 8, 2, this._litColor([244, 246, 252], [96, 114, 148], ch, 0.12));
    const ledBlink = reducedMotion ? 1 : (0.5 + 0.5 * Math.sin(animTime * 2.2));
    this.px(199, 52, 1, 1, [88, 244, 156], 0.55 + 0.45 * ledBlink);

    this.px(169, 65, 14, 10, this._litColor([198, 158, 114], [96, 74, 58], ch, 0.22));
    this.px(170, 68, 12, 1, this._litColor([168, 128, 86], [76, 56, 44], ch, 0.2));
    this.px(170, 71, 12, 1, this._litColor([168, 128, 86], [76, 56, 44], ch, 0.2));
    this.px(186, 66, 15, 3, this._litColor([102, 148, 206], [46, 76, 124], ch, 0.12));
    this.px(187, 69, 14, 3, this._litColor([228, 234, 244], [52, 68, 104], ch, 0.15));
    this.px(186, 72, 15, 3, this._litColor([236, 128, 112], [116, 62, 68], ch, 0.15));

    const potCol = this._litColor([212, 126, 86], [108, 62, 52], ch, 0.22);
    const leafDark = this._litColor([58, 128, 88], [22, 56, 54], ch, 0.12);
    const leafLight = this._litColor([102, 182, 118], [38, 86, 76], ch, 0.14);

    this.px(190, 17, 11, 9, potCol);
    this.px(188, 16, 15, 3, this._litColor([228, 148, 106], [122, 74, 62], ch, 0.22));

    const sway = reducedMotion ? 0 : Math.round(Math.sin(animTime * 1.4) * 0.8);
    this.px(187, 13, 6, 4, leafDark);
    this.px(192, 10, 8, 6, leafLight);
    this.px(199, 13, 6, 4, leafDark);
    this.px(202 + sway, 18, 3, 6, leafLight);
    this.px(204 + sway, 24, 3, 7, leafDark);
    this.px(205 + sway, 31, 3, 6, leafLight);
    this.px(206 + sway, 37, 2, 5, leafDark);
    this.px(186 - sway, 18, 3, 6, leafLight);
    this.px(184 - sway, 24, 3, 5, leafDark);
  }

  _drawWorkstationAndWorker(ch, animTime, transitionActivity, reducedMotion) {
    this.px(72, 94, 86, 6, [10, 18, 38], 0.36 + ch.darkness * 0.28);

    const deskTop   = this._litColor([118, 138, 166], [34, 49, 82], ch, 0.22);
    const deskFront = this._litColor([84, 104, 134], [24, 36, 64], ch, 0.18);
    const deskDark  = this._litColor([62, 78, 104], [16, 25, 46], ch, 0.15);

    this.px(75, 72, 4, 25, deskDark);
    this.px(81, 79, 9, 17, this._litColor([54, 64, 84], [16, 22, 40], ch, 0.12));
    this.px(82, 81, 7, 2, this._litColor([72, 84, 108], [26, 36, 62], ch, 0.10));
    const pcLed = reducedMotion ? 1 : (0.4 + 0.6 * Math.sin(animTime * 4.5));
    this.px(83, 84, 2, 1, [92, 214, 255], 0.6 + 0.4 * ch.monitorEmission);
    this.px(86, 84, 1, 1, [110, 248, 168], pcLed * 0.85);

    this.px(134, 72, 21, 25, deskFront);
    this.px(136, 74, 17, 6, deskTop);
    this.px(136, 82, 17, 6, deskTop);
    this.px(136, 90, 17, 6, deskTop);
    this.px(143, 76, 3, 1, deskDark);
    this.px(143, 84, 3, 1, deskDark);
    this.px(143, 92, 3, 1, deskDark);

    this.px(72, 69, 85, 4, deskTop);
    this.px(72, 72, 85, 1, deskDark);
    this.px(95, 69, 32, 1, deskDark);

    const bezelCol = this._litColor([54, 64, 82], [16, 23, 42], ch, 0.10);
    this.px(107, 64, 6, 4, bezelCol);
    this.px(102, 67, 16, 2, bezelCol);
    this.px(96, 45, 28, 19, bezelCol);
    this.px(121, 63, 1, 1, [104, 232, 180], 0.85);

    const codeBlend = MathUtils.smoothstep(0.20, 0.78, ch.monitorEmission);
    const screenBg = MathUtils.lerpRGB([236, 242, 252], [15, 24, 48], codeBlend);
    this.px(98, 47, 24, 15, screenBg);

    if (codeBlend < 0.55) {
      const uiA = MathUtils.clamp(1 - codeBlend * 1.8, 0, 1);
      this.px(98, 47, 24, 3, [174, 194, 220], uiA);
      this.px(98, 50, 6, 12, [208, 220, 236], uiA);
      this.px(106, 52, 13, 1, [144, 164, 192], uiA);
      this.px(106, 54, 10, 1, [164, 182, 206], uiA);
      this.px(106, 56, 12, 1, [164, 182, 206], uiA);
      this.px(106, 59, 4, 2, [108, 174, 238], uiA);
      this.px(111, 58, 4, 3, [94, 196, 164], uiA);
    }
    if (codeBlend > 0.22) {
      const cA = MathUtils.smoothstep(0.22, 0.70, codeBlend);
      this.px(98, 47, 4, 15, [22, 34, 66], cA);
      this.px(102, 47, 20, 2, [26, 40, 74], cA);
      const typeLen = reducedMotion ? 6 : (2 + Math.floor((animTime * 4.5) % 8));
      const cursorOn = reducedMotion ? 1 : (Math.sin(animTime * 7.5) > 0 ? 1 : 0);

      this.px(104, 50, 4, 1, [246, 114, 186], cA);
      this.px(109, 50, 8, 1, [104, 224, 255], cA);
      this.px(105, 52, 6, 1, [255, 204, 106], cA);
      this.px(112, 52, 7, 1, [154, 232, 188], cA);
      this.px(105, 54, 9, 1, [118, 206, 255], cA);
      this.px(115, 54, 4, 1, [250, 126, 192], cA);
      this.px(104, 56, 5, 1, [255, 178, 92], cA);
      this.px(110, 56, typeLen, 1, [132, 236, 255], cA);
      if (cursorOn) {
        this.px(110 + typeLen, 56, 1, 1, [255, 255, 255], cA);
      }
      this.px(98, 60, 24, 2, [46, 90, 174], cA);
    }

    this.px(99, 68, 16, 1, this._litColor([184, 194, 212], [58, 76, 116], ch, 0.1));
    this.px(118, 68, 3, 1, this._litColor([196, 206, 222], [70, 88, 128], ch, 0.1));
    this.px(124, 68, 7, 1, this._litColor([246, 244, 236], [88, 94, 118], ch, 0.18));

    this.px(80, 64, 5, 5, this._litColor([246, 248, 252], [82, 98, 134], ch, 0.18));
    this.px(85, 65, 1, 3, this._litColor([210, 218, 230], [58, 72, 104], ch, 0.15));
    this.px(81, 64, 3, 1, this._litColor([136, 92, 66], [68, 44, 36], ch, 0.15));
    if (!reducedMotion) {
      const s1 = Math.floor((animTime * 2.2) % 5);
      const s2 = Math.floor((animTime * 2.2 + 2.5) % 5);
      const steamCol = this._litColor([255, 255, 255], [176, 200, 238], ch, 0.1);
      this.px(81 + (s1 % 2), 62 - s1, 1, 1, steamCol, 0.45 * (1 - s1 / 5));
      this.px(83 - (s2 % 2), 62 - s2, 1, 1, steamCol, 0.40 * (1 - s2 / 5));
    }

    const lampMetal = this._litColor([72, 86, 112], [38, 48, 76], ch, 0.15);
    const lampShade = this._litColor([94, 110, 138], [58, 66, 94], ch, 0.2);
    this.px(139, 68, 10, 1, lampMetal);
    this.px(141, 66, 6, 2, lampMetal);
    this.px(143, 58, 2, 8, lampMetal);
    this.px(141, 55, 3, 3, lampMetal);
    this.px(138, 52, 3, 3, lampMetal);
    this.px(132, 50, 9, 4, lampShade);
    this.px(130, 53, 9, 3, lampMetal);

    if (ch.deskLampEmission > 0.03) {
      this.px(130, 56, 8, 2, [255, 240, 168], MathUtils.clamp(ch.deskLampEmission * 1.1, 0, 1));
      this.px(132, 55, 5, 1, [255, 250, 224], MathUtils.clamp(ch.deskLampEmission, 0, 1));
    }

    const isNightFocus = ch.darkness > 0.45;
    const typeCycle = reducedMotion ? 0 : Math.floor(animTime * (isNightFocus ? 6.5 : 3.8)) % 4;
    const headBob = reducedMotion ? 0 : (Math.sin(animTime * 1.9) > 0.80 ? 1 : 0);
    const blink = !reducedMotion && ((animTime % 4.3) > 4.16);
    const leanX = (transitionActivity > 0.15 || isNightFocus) ? 2 : 0;

    const hairCol  = this._litColor([38, 42, 58], [16, 20, 36], ch, 0.1);
    const skinCol  = this._litColor([242, 202, 176], [150, 120, 114], ch, 0.25);
    const shirtCol = this._litColor([232, 237, 246], [86, 104, 142], ch, 0.20);
    const shirtShd = this._litColor([204, 212, 228], [62, 78, 112], ch, 0.18);
    const pantsCol = this._litColor([56, 70, 96], [22, 32, 56], ch, 0.15);

    const wx = 98 + leanX;
    this.px(wx + 2, 78, 4, 14, pantsCol);
    this.px(wx + 8, 78, 4, 14, pantsCol);
    this.px(wx + 2, 92, 6, 3, hairCol);
    this.px(wx + 8, 92, 6, 3, hairCol);

    this.px(wx + 1, 65, 11, 14, shirtCol);
    this.px(wx + 1, 65, 3, 14, shirtShd);
    if (ch.monitorEmission > 0.32) {
      this.px(wx + 9, 65, 3, 9, [130, 183, 255], (ch.monitorEmission - 0.32) * 0.45);
    }

    const leftArmY = (typeCycle === 0 || typeCycle === 2) ? 67 : 68;
    const rightArmY = (typeCycle === 1 || typeCycle === 3) ? 67 : 68;
    this.px(wx + 9, leftArmY, 6, 3, shirtCol);
    this.px(wx + 14, leftArmY, 3, 2, skinCol);
    this.px(wx + 6, rightArmY + 2, 6, 3, shirtShd);

    const hy = 53 + headBob;
    this.px(wx + 3, hy + 3, 9, 9, skinCol);
    this.px(wx + 2, hy, 10, 4, hairCol);
    this.px(wx + 1, hy + 2, 3, 7, hairCol);
    this.px(wx + 4, hy + 3, 4, 1, hairCol);
    if (!blink) {
      this.px(wx + 9, hy + 6, 2, 2, hairCol);
    } else {
      this.px(wx + 9, hy + 7, 2, 1, hairCol);
    }

    const chairFrame = this._litColor([46, 54, 72], [15, 21, 36], ch, 0.1);
    const chairMesh  = this._litColor([144, 158, 182], [44, 58, 88], ch, 0.15);

    this.px(97, 83, 3, 11, chairFrame);
    this.px(90, 93, 18, 3, chairFrame);
    this.px(90, 96, 3, 2, chairFrame);
    this.px(105, 96, 3, 2, chairFrame);
    this.px(91, 80, 17, 4, chairFrame);
    this.px(89, 61, 5, 20, chairFrame);
    this.px(91, 63, 3, 15, chairMesh);
    this.px(93, 74, 9, 2, chairFrame);
  }

  _drawLocalLightSources(ch, animTime, reducedMotion) {
    const ctx = this.ctx;

    if (ch.monitorEmission > 0.25) {
      const mAlpha = (ch.monitorEmission - 0.25) * 0.44;
      const grad = ctx.createRadialGradient(110, 55, 3, 110, 57, 34);
      grad.addColorStop(0, `rgba(130, 183, 255, ${(mAlpha * 1.12).toFixed(3)})`);
      grad.addColorStop(0.5, `rgba(92, 148, 240, ${(mAlpha * 0.46).toFixed(3)})`);
      grad.addColorStop(1, 'rgba(92, 148, 240, 0)');
      ctx.save();
      ctx.globalCompositeOperation = 'screen';
      ctx.fillStyle = grad;
      ctx.fillRect(72, 22, 80, 68);
      ctx.restore();
    }

    if (ch.deskLampEmission > 0.02) {
      const e = ch.deskLampEmission;
      const shimmer = 0.985 + 0.015 * Math.sin(animTime * 3.1);
      const intensity = e * shimmer;

      ctx.save();
      ctx.globalCompositeOperation = 'screen';

      const outerGrad = ctx.createRadialGradient(134, 61, 3, 134, 66, 52);
      outerGrad.addColorStop(0.00, `rgba(255, 240, 168, ${(0.84 * intensity).toFixed(3)})`);
      outerGrad.addColorStop(0.24, `rgba(255, 214, 111, ${(0.56 * intensity).toFixed(3)})`);
      outerGrad.addColorStop(0.54, `rgba(245, 173, 72, ${(0.25 * intensity).toFixed(3)})`);
      outerGrad.addColorStop(0.84, `rgba(224, 128, 44, ${(0.08 * intensity).toFixed(3)})`);
      outerGrad.addColorStop(1.00, 'rgba(224, 128, 44, 0)');
      ctx.fillStyle = outerGrad;
      ctx.fillRect(78, 20, 118, 98);

      const coneGrad = ctx.createRadialGradient(134, 68, 2, 134, 68, 17);
      coneGrad.addColorStop(0, `rgba(255, 244, 196, ${(0.78 * intensity).toFixed(3)})`);
      coneGrad.addColorStop(0.55, `rgba(255, 214, 111, ${(0.38 * intensity).toFixed(3)})`);
      coneGrad.addColorStop(1, 'rgba(245, 173, 72, 0)');
      ctx.fillStyle = coneGrad;
      ctx.fillRect(114, 52, 40, 32);

      ctx.restore();

      if (!reducedMotion && e > 0.35) {
        const moteA = MathUtils.smoothstep(0.35, 0.9, e) * 0.65;
        for (const m of this.dustMotes) {
          const mx = m.bx + Math.sin(animTime * m.speed + m.phase) * 4;
          const my = m.by + Math.cos(animTime * m.speed * 0.7 + m.phase) * 3;
          this.px(mx, my, 1, 1, [255, 242, 192], moteA);
        }
      }
    }
  }
}

class LiquidGlassRenderer {
  constructor(displayCanvas, scene, canvas2D) {
    this.canvas = displayCanvas;
    this.scene = scene;
    this.mode = 'webgl';
    this.gl = null;
    this.ctx2d = null;
    this.program = null;
    this.texture = null;
    this.uniforms = {};
    this.disposed = false;

    this._initContext(canvas2D);
  }

  _initContext(canvas2D) {
    if (!canvas2D) {
      try {
        const gl = this.canvas.getContext('webgl', { alpha: false, antialias: true, powerPreference: 'low-power' });
        if (gl) {
          this.gl = gl;
          this._setupWebGL(gl);
          return;
        }
      } catch {
        // A canvas that acquired a WebGL context cannot subsequently acquire a 2D one.
        this._releaseWebGL();
        this.canvas = document.createElement('canvas');
      }
    }

    this.mode = 'canvas2d';
    this.ctx2d = this.canvas.getContext('2d', { alpha: false });
    if (!this.ctx2d) throw new Error('No canvas renderer available');
  }

  _compileShader(gl, type, source) {
    const shader = gl.createShader(type);
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
      const log = gl.getShaderInfoLog(shader);
      gl.deleteShader(shader);
      throw new Error('Shader compile failed: ' + log);
    }
    return shader;
  }

  _setupWebGL(gl) {
    const vsSource = `
      attribute vec2 aPos;
      varying vec2 vUv;
      void main() {
        vUv = vec2(aPos.x * 0.5 + 0.5, 0.5 - aPos.y * 0.5);
        gl_Position = vec4(aPos, 0.0, 1.0);
      }
    `;

    const fsSource = `
      precision highp float;
      varying vec2 vUv;

      uniform sampler2D uScene;
      uniform vec2 uResolution;
      uniform vec2 uSceneSize;
      uniform float uLensX;
      uniform float uLensRadius;
      uniform float uStretchX;
      uniform float uVelocity;
      uniform float uGlassReflect;
      uniform float uDarkness;
      uniform float uLampEmission;
      uniform float uSunsetWarmth;
      uniform float uSunriseWarmth;

      vec3 samplePixel(vec2 uv) {
        vec2 clamped = clamp(uv, vec2(0.002), vec2(0.998));
        vec2 snapped = (floor(clamped * uSceneSize) + 0.5) / uSceneSize;
        return texture2D(uScene, snapped).rgb;
      }

      vec3 sampleOptical(vec2 uv, float softness) {
        vec3 crisp = samplePixel(uv);
        vec3 linear = texture2D(uScene, clamp(uv, vec2(0.002), vec2(0.998))).rgb;
        return mix(crisp, linear, softness);
      }

      void main() {
        float aspect = uResolution.x / max(uResolution.y, 1.0);
        vec2 lensCenter = vec2(uLensX, 0.5);

        vec2 rel = vec2((vUv.x - lensCenter.x) * aspect, vUv.y - lensCenter.y);
        vec2 relStretched = vec2(rel.x / uStretchX, rel.y);
        float dist = length(relStretched);
        float rNorm = dist / uLensRadius;

        vec3 baseColor = samplePixel(vUv);

        vec2 shadowRel = vec2(((vUv.x - lensCenter.x) * aspect - 0.012) / uStretchX, (vUv.y - lensCenter.y) - 0.032);
        float shadowDist = length(shadowRel) / uLensRadius;
        if (rNorm >= 1.0) {
          float castShadow = (1.0 - smoothstep(0.96, 1.24, shadowDist)) * (0.28 + uDarkness * 0.24);
          float causticSpot = (1.0 - smoothstep(0.98, 1.16, shadowDist)) * smoothstep(0.86, 1.02, shadowDist);
          vec3 causticTint = mix(vec3(0.92, 0.96, 1.0), vec3(0.62, 0.78, 1.0), uDarkness);
          baseColor = baseColor * (1.0 - castShadow) + causticTint * causticSpot * (0.14 * (1.0 - uDarkness * 0.55));
          gl_FragColor = vec4(baseColor, 1.0);
          return;
        }

        vec2 dir = dist > 0.0001 ? (relStretched / dist) : vec2(0.0);
        float z = sqrt(max(0.001, 1.0 - rNorm * rNorm));
        vec3 normal = normalize(vec3(relStretched / uLensRadius, z * 0.82));

        float centerMag = 0.83;
        float rimWrap = pow(smoothstep(0.58, 1.0, rNorm), 2.15) * 0.46;
        float radialScale = mix(centerMag, 0.42, rimWrap);

        vec2 refractedRel = relStretched * radialScale;
        vec2 edgePull = -normal.xy * pow(rNorm, 3.2) * uLensRadius * 0.16;
        vec2 refractedUv = lensCenter + vec2((refractedRel.x + edgePull.x) * uStretchX / aspect, refractedRel.y + edgePull.y);

        float caStrength = pow(rNorm, 3.0) * 0.011 * (0.85 + 0.35 * uGlassReflect);
        vec2 caOffset = vec2(dir.x / aspect, dir.y) * caStrength;
        float edgeSoft = smoothstep(0.76, 1.0, rNorm) * 0.45;

        float colR = sampleOptical(refractedUv + caOffset, edgeSoft).r;
        float colG = sampleOptical(refractedUv, edgeSoft * 0.5).g;
        float colB = sampleOptical(refractedUv - caOffset, edgeSoft).b;
        vec3 glassColor = vec3(colR, colG, colB);

        vec3 dayGlassTint = vec3(0.95, 0.98, 1.0);
        vec3 nightGlassTint = vec3(0.76, 0.85, 1.0);
        vec3 volumeTint = mix(dayGlassTint, nightGlassTint, uDarkness);
        float thicknessShade = smoothstep(0.72, 1.0, rNorm) * (0.14 + uDarkness * 0.14);
        glassColor = glassColor * mix(vec3(1.0), volumeTint, 0.18 + rNorm * 0.25) * (1.0 - thicknessShade);

        float fresnel = pow(1.0 - clamp(normal.z, 0.0, 1.0), 2.8);
        vec3 envReflectCol = mix(vec3(0.92, 0.96, 1.0), vec3(0.42, 0.56, 0.92), uDarkness);
        if (uSunsetWarmth > 0.02) {
          envReflectCol = mix(envReflectCol, vec3(1.0, 0.78, 0.54), uSunsetWarmth * 0.45);
        }
        if (uSunriseWarmth > 0.02) {
          envReflectCol = mix(envReflectCol, vec3(1.0, 0.82, 0.76), uSunriseWarmth * 0.42);
        }
        glassColor += envReflectCol * fresnel * (0.42 * uGlassReflect + 0.12);

        vec2 lightDirTop = normalize(vec3(-0.24 - uVelocity * 0.08, -0.78, 0.68)).xy;
        float topCrescent = smoothstep(0.78, 0.96, dot(normalize(relStretched + vec2(0.0001)), lightDirTop))
                          * smoothstep(0.62, 0.88, rNorm)
                          * (1.0 - smoothstep(0.93, 0.995, rNorm));
        glassColor += vec3(1.0, 0.99, 1.0) * topCrescent * (0.62 * uGlassReflect + 0.14);

        vec2 domePos = (relStretched / uLensRadius) - vec2(-0.14 - uVelocity * 0.04, -0.44);
        float upperDome = exp(-dot(domePos * vec2(1.4, 2.6), domePos * vec2(1.4, 2.6)) * 5.2);
        glassColor += vec3(0.96, 0.98, 1.0) * upperDome * (0.20 * uGlassReflect + 0.04);

        vec2 lightDirBot = normalize(vec2(0.18, 0.86));
        float botArc = smoothstep(0.70, 0.95, dot(normalize(relStretched + vec2(0.0001)), lightDirBot))
                     * smoothstep(0.72, 0.92, rNorm)
                     * (1.0 - smoothstep(0.95, 1.0, rNorm));
        vec3 botCol = mix(vec3(0.86, 0.94, 1.0), vec3(0.48, 0.66, 1.0), uDarkness);
        glassColor += botCol * botArc * (0.44 * uGlassReflect + 0.14);

        if (uLampEmission > 0.02) {
          float lampScreenX = 134.0 / 222.0;
          float lampDelta = clamp((lampScreenX - uLensX) * 2.2, -0.7, 0.7);
          vec2 lampReflPos = (relStretched / uLensRadius) - vec2(lampDelta * 0.65, 0.18);
          float lampGlint = exp(-dot(lampReflPos, lampReflPos) * 7.0) * smoothstep(0.25, 0.95, rNorm);
          glassColor += vec3(1.0, 0.82, 0.44) * lampGlint * uLampEmission * 0.36;
        }

        float rimLine = smoothstep(0.945, 0.982, rNorm) * (1.0 - smoothstep(0.985, 1.0, rNorm));
        vec3 rimCol = mix(vec3(1.0, 1.0, 1.0), vec3(0.64, 0.78, 1.0), uDarkness);
        glassColor += rimCol * rimLine * (0.58 * uGlassReflect + 0.20);

        float aaEdge = 1.0 - smoothstep(0.982, 1.0, rNorm);
        vec3 finalColor = mix(baseColor, glassColor, aaEdge);
        gl_FragColor = vec4(finalColor, 1.0);
      }
    `;

    const vs = this._compileShader(gl, gl.VERTEX_SHADER, vsSource);
    const fs = this._compileShader(gl, gl.FRAGMENT_SHADER, fsSource);
    const prog = gl.createProgram();
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    gl.deleteShader(vs);
    gl.deleteShader(fs);
    this.program = prog;
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      throw new Error('Program link failed: ' + gl.getProgramInfoLog(prog));
    }

    gl.useProgram(prog);

    const quad = new Float32Array([-1, -1, 1, -1, -1, 1, 1, 1]);
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, quad, gl.STATIC_DRAW);
    const aPos = gl.getAttribLocation(prog, 'aPos');
    gl.enableVertexAttribArray(aPos);
    gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
    this.vertexBuffer = buf;

    const tex = gl.createTexture();
    gl.activeTexture(gl.TEXTURE0);
    gl.bindTexture(gl.TEXTURE_2D, tex);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
    gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, this.scene.width, this.scene.height, 0, gl.RGBA, gl.UNSIGNED_BYTE, null);
    this.texture = tex;

    this.uniforms = {
      uScene: gl.getUniformLocation(prog, 'uScene'),
      uResolution: gl.getUniformLocation(prog, 'uResolution'),
      uSceneSize: gl.getUniformLocation(prog, 'uSceneSize'),
      uLensX: gl.getUniformLocation(prog, 'uLensX'),
      uLensRadius: gl.getUniformLocation(prog, 'uLensRadius'),
      uStretchX: gl.getUniformLocation(prog, 'uStretchX'),
      uVelocity: gl.getUniformLocation(prog, 'uVelocity'),
      uGlassReflect: gl.getUniformLocation(prog, 'uGlassReflect'),
      uDarkness: gl.getUniformLocation(prog, 'uDarkness'),
      uLampEmission: gl.getUniformLocation(prog, 'uLampEmission'),
      uSunsetWarmth: gl.getUniformLocation(prog, 'uSunsetWarmth'),
      uSunriseWarmth: gl.getUniformLocation(prog, 'uSunriseWarmth')
    };
    gl.uniform1i(this.uniforms.uScene, 0);
    gl.uniform2f(this.uniforms.uSceneSize, this.scene.width, this.scene.height);
  }

  resize(cssWidth, cssHeight) {
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const w = Math.max(1, Math.round(cssWidth * dpr));
    const h = Math.max(1, Math.round(cssHeight * dpr));
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    if (this.gl) {
      this.gl.viewport(0, 0, w, h);
      this.gl.uniform2f(this.uniforms.uResolution, w, h);
    }
  }

  render(state) {
    if (this.disposed) return;
    const { lensProgress, stretchX, velocity, channels } = state;

    const aspect = this.canvas.width / Math.max(this.canvas.height, 1);
    const radiusV = 0.42;
    const marginX = (radiusV + 0.055) / aspect;
    const lensX = MathUtils.lerp(marginX, 1.0 - marginX, lensProgress);

    if (this.mode === 'webgl' && this.gl) {
      const gl = this.gl;
      gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, gl.RGBA, gl.UNSIGNED_BYTE, this.scene.canvas);

      gl.uniform1f(this.uniforms.uLensX, lensX);
      gl.uniform1f(this.uniforms.uLensRadius, radiusV);
      gl.uniform1f(this.uniforms.uStretchX, stretchX);
      gl.uniform1f(this.uniforms.uVelocity, velocity);
      gl.uniform1f(this.uniforms.uGlassReflect, channels.glassReflectionIntensity);
      gl.uniform1f(this.uniforms.uDarkness, channels.darkness);
      gl.uniform1f(this.uniforms.uLampEmission, channels.deskLampEmission);
      gl.uniform1f(this.uniforms.uSunsetWarmth, channels.sunsetWarmth);
      gl.uniform1f(this.uniforms.uSunriseWarmth, channels.sunriseWarmth);

      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    } else if (this.ctx2d) {
      this._render2DFallback(lensX, radiusV, stretchX, channels);
    }
  }

  _render2DFallback(lensX, radiusV, stretchX, ch) {
    const ctx = this.ctx2d;
    const W = this.canvas.width;
    const H = this.canvas.height;

    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.scene.canvas, 0, 0, W, H);

    const cx = lensX * W;
    const cy = H * 0.5;
    const r = radiusV * H;

    ctx.save();
    ctx.beginPath();
    ctx.ellipse(cx + 3, cy + 7, r * stretchX * 1.03, r * 1.03, 0, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(8, 14, 32, ${(0.22 + ch.darkness * 0.24).toFixed(3)})`;
    ctx.fill();
    ctx.restore();

    ctx.save();
    ctx.beginPath();
    ctx.ellipse(cx, cy, r * stretchX, r, 0, 0, Math.PI * 2);
    ctx.clip();

    const mag = 1.24;
    const srcW = (r * 2 / W) * this.scene.width / mag;
    const srcH = (r * 2 / H) * this.scene.height / mag;
    const srcX = MathUtils.clamp(lensX * this.scene.width - srcW * 0.5, 0, this.scene.width - srcW);
    const srcY = MathUtils.clamp(0.5 * this.scene.height - srcH * 0.5, 0, this.scene.height - srcH);
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.scene.canvas, srcX, srcY, srcW, srcH, cx - r * stretchX, cy - r, r * 2 * stretchX, r * 2);

    const rimGrad = ctx.createRadialGradient(cx, cy, r * 0.62, cx, cy, r);
    rimGrad.addColorStop(0, 'rgba(255,255,255,0)');
    rimGrad.addColorStop(0.82, `rgba(210,232,255,${(0.18 * ch.glassReflectionIntensity).toFixed(3)})`);
    rimGrad.addColorStop(1, `rgba(255,255,255,${(0.55 * ch.glassReflectionIntensity + 0.15).toFixed(3)})`);
    ctx.fillStyle = rimGrad;
    ctx.fillRect(cx - r * stretchX, cy - r, r * 2 * stretchX, r * 2);

    ctx.beginPath();
    ctx.ellipse(cx - r * 0.12, cy - r * 0.52, r * 0.52, r * 0.18, -0.18, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(255,255,255,${(0.32 * ch.glassReflectionIntensity + 0.08).toFixed(3)})`;
    ctx.fill();
    ctx.restore();
  }

  dispose() {
    this.disposed = true;
    this._releaseWebGL();
  }

  _releaseWebGL() {
    if (!this.gl) return;
    if (this.texture) this.gl.deleteTexture(this.texture);
    if (this.vertexBuffer) this.gl.deleteBuffer(this.vertexBuffer);
    if (this.program) this.gl.deleteProgram(this.program);
    this.gl.getExtension('WEBGL_lose_context')?.loseContext();
    this.gl = null;
  }
}

export { MathUtils, LightingEngine, PixelOfficeScene, LiquidGlassRenderer };
