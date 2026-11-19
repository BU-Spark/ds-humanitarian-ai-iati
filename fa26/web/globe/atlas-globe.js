import * as THREE from 'three';
import {EffectComposer} from 'three/examples/jsm/postprocessing/EffectComposer.js';
import {RenderPass} from 'three/examples/jsm/postprocessing/RenderPass.js';
import {UnrealBloomPass} from 'three/examples/jsm/postprocessing/UnrealBloomPass.js';
import {OutputPass} from 'three/examples/jsm/postprocessing/OutputPass.js';

export function mountGlobe(opts) {
  const {canvas, data, pts, ptsB64, labelsEl, onReady, avoid, topInset = 64, gap = 32} = opts;   // avoid: element the globe must never cover
  const RM = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const PUB = {'Oxfam GB': '#FF7A45', 'Oxfam America': '#5BA8FF', 'WFP': '#3DDC97'};
  const deg = Math.PI / 180;
  const vec = (lat, lon, r = 1) => new THREE.Vector3(r * Math.cos(lat * deg) * Math.sin(lon * deg), r * Math.sin(lat * deg), r * Math.cos(lat * deg) * Math.cos(lon * deg));

  // ---------- renderer, scene, camera ----------
  const renderer = new THREE.WebGLRenderer({canvas, antialias: false, alpha: false, powerPreference: 'high-performance'});
  let DPR = Math.min(devicePixelRatio || 1, 2);
  renderer.setPixelRatio(DPR);
  renderer.setClearColor(0x03050B, 1);
  const scene = new THREE.Scene(); scene.background = new THREE.Color(0x03050B);
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 200);
  camera.position.set(0, 0, RM ? 3.5 : 10);
  const world = new THREE.Group();          // moves left/right with layout
  const globe = new THREE.Group();          // rotates to bring a place to the front
  world.add(globe); scene.add(world);

  // ---------- stars ----------
  {
    const n = 2600, p = new Float32Array(n * 3), s = new Float32Array(n), ph = new Float32Array(n), c = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const u = Math.random() * 2 - 1, t = Math.random() * Math.PI * 2, r = 40 + Math.random() * 60, q = Math.sqrt(1 - u * u);
      p.set([r * q * Math.cos(t), r * u, r * q * Math.sin(t) - 20], i * 3);
      s[i] = Math.random() < .06 ? 2.6 + Math.random() * 1.6 : .8 + Math.random() * 1.2; ph[i] = Math.random() * 6.28;
      const warm = Math.random(); c.set(warm < .15 ? [1, .85, .7] : warm < .35 ? [.7, .8, 1] : [.85, .88, .95], i * 3);
    }
    const g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.BufferAttribute(p, 3)); g.setAttribute('aSize', new THREE.BufferAttribute(s, 1));
    g.setAttribute('aPhase', new THREE.BufferAttribute(ph, 1)); g.setAttribute('aColor', new THREE.BufferAttribute(c, 3));
    var stars = new THREE.Points(g, new THREE.ShaderMaterial({
      uniforms: {uTime: {value: 0}, uDpr: {value: DPR}}, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: `attribute float aSize;attribute float aPhase;attribute vec3 aColor;uniform float uTime;uniform float uDpr;varying vec3 vC;varying float vA;
        void main(){vC=aColor;vA=.35+.35*sin(uTime*.8+aPhase);vec4 mv=modelViewMatrix*vec4(position,1.);gl_PointSize=aSize*uDpr;gl_Position=projectionMatrix*mv;}`,
      fragmentShader: `varying vec3 vC;varying float vA;void main(){float d=length(gl_PointCoord-.5);float a=smoothstep(.5,0.,d);gl_FragColor=vec4(vC,a*vA);}`
    }));
    scene.add(stars);
  }

  // ---------- ocean sphere with fresnel rim ----------
  const ocean = new THREE.Mesh(new THREE.SphereGeometry(.995, 96, 96), new THREE.ShaderMaterial({
    uniforms: {uBase: {value: new THREE.Color('#02040B')}, uRim: {value: new THREE.Color('#123A8C')}},
    vertexShader: `varying vec3 vN;varying vec3 vV;void main(){vec4 mv=modelViewMatrix*vec4(position,1.);vN=normalize(normalMatrix*normal);vV=normalize(-mv.xyz);gl_Position=projectionMatrix*mv;}`,
    fragmentShader: `uniform vec3 uBase;uniform vec3 uRim;varying vec3 vN;varying vec3 vV;
      void main(){float f=pow(1.-max(dot(vN,vV),0.),3.2);vec3 col=mix(uBase,uRim,f*.7);
      float lit=.7+.3*max(dot(vN,normalize(vec3(-.6,.5,.7))),0.);gl_FragColor=vec4(col*lit,1.);}`
  }));
  globe.add(ocean);

  // ---------- atmosphere (back-face, additive) ----------
  const atmo = new THREE.Mesh(new THREE.SphereGeometry(1.0, 96, 96), new THREE.ShaderMaterial({
    uniforms: {uC: {value: new THREE.Color('#3D7CFF')}}, side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    vertexShader: `varying vec3 vN;varying vec3 vV;void main(){vec4 mv=modelViewMatrix*vec4(position,1.);vN=normalize(normalMatrix*normal);vV=normalize(-mv.xyz);gl_Position=projectionMatrix*mv;}`,
    fragmentShader: `uniform vec3 uC;varying vec3 vN;varying vec3 vV;void main(){float i=pow(smoothstep(0.,.55,-dot(vN,vV)),2.4)*.55;gl_FragColor=vec4(uC*i,i);}`
  }));
  atmo.scale.setScalar(1.13); world.add(atmo);

  // ---------- land dots ----------
  const names = Object.keys(data.countries);
  const maxAct = Math.max(...Object.values(data.activities));
  const raw = pts || new Int16Array(Uint8Array.from(atob(ptsB64), c => c.charCodeAt(0)).buffer);
  const n = raw.length / 3;
  const P = new Float32Array(n * 3), C = new Float32Array(n * 3), S = new Float32Array(n), PH = new Float32Array(n), CI = new Float32Array(n);
  const dim = new THREE.Color('#3A5C8C'), dim2 = new THREE.Color('#22395C'), lo = new THREE.Color('#B8741E'), hi = new THREE.Color('#F2C46A'), tmp = new THREE.Color();
  for (let i = 0; i < n; i++) {
    const lat = raw[i * 3] / 100, lon = raw[i * 3 + 1] / 100, ci = raw[i * 3 + 2];
    const v = vec(lat, lon, 1.0); P.set([v.x, v.y, v.z], i * 3); PH[i] = Math.random() * 6.28; CI[i] = ci;
    if (ci > 0) {
      const w = (data.activities[names[ci - 1]] || 0) / maxAct;
      tmp.copy(lo).lerp(hi, Math.pow(w, 1.4)); C.set([tmp.r, tmp.g, tmp.b], i * 3); S[i] = 1.5 + .8 * w;
    } else {
      tmp.copy(dim2).lerp(dim, Math.random()); C.set([tmp.r, tmp.g, tmp.b], i * 3); S[i] = 2.4;
    }
  }
  const lg = new THREE.BufferGeometry();
  lg.setAttribute('position', new THREE.BufferAttribute(P, 3)); lg.setAttribute('aColor', new THREE.BufferAttribute(C, 3));
  lg.setAttribute('aSize', new THREE.BufferAttribute(S, 1)); lg.setAttribute('aPhase', new THREE.BufferAttribute(PH, 1)); lg.setAttribute('aCi', new THREE.BufferAttribute(CI, 1));
  const landMat = new THREE.ShaderMaterial({
    uniforms: {uTime: {value: 0}, uDpr: {value: DPR}, uScale: {value: 1}, uFocus: {value: 0}, uFocusAmt: {value: 0}, uReveal: {value: RM ? 1 : 0}},
    transparent: true, depthWrite: false,
    vertexShader: `attribute vec3 aColor;attribute float aSize;attribute float aPhase;attribute float aCi;
      uniform float uTime;uniform float uDpr;uniform float uScale;uniform float uFocus;uniform float uFocusAmt;uniform float uReveal;
      varying vec3 vC;varying float vA;
      void main(){vec4 mv=modelViewMatrix*vec4(position,1.);vec3 n=normalize(normalMatrix*position);float facing=dot(n,normalize(-mv.xyz));
        float aid=step(.5,aCi);float isF=1.-step(.5,abs(aCi-uFocus));
        float tw=aid>0.?.78+.22*sin(uTime*2.2+aPhase):1.;
        float boost=mix(1.,mix(.3,1.35,isF),uFocusAmt*aid);
        float rv=smoothstep(0.,1.,clamp(uReveal*1.6-(position.y*.5+.5)*.6,0.,1.));
        vC=min(aColor*tw*boost,vec3(.95));vA=smoothstep(-.05,.35,facing)*rv*(aid>0.?1.:.85);
        gl_PointSize=aSize*uDpr*uScale*(3.4/-mv.z)*(aid>0.?1.:.9);gl_Position=projectionMatrix*mv;}`,
    fragmentShader: `varying vec3 vC;varying float vA;void main(){float d=length(gl_PointCoord-.5);if(d>.5)discard;float a=smoothstep(.5,.28,d);gl_FragColor=vec4(vC,a*vA);}`
  });
  const land = new THREE.Points(lg, landMat); globe.add(land);

  // ---------- arcs: glowing pulses from publisher HQ to country ----------
  const maxLink = Math.max(...data.links.map(l => l.activities));
  const arcs = [];
  const slerpPt = (a, b, t) => { const q = new THREE.Vector3().copy(a).normalize(), w = new THREE.Vector3().copy(b).normalize(); const om = Math.acos(THREE.MathUtils.clamp(q.dot(w), -1, 1)); if (om < 1e-4) return q; return q.multiplyScalar(Math.sin((1 - t) * om) / Math.sin(om)).add(w.multiplyScalar(Math.sin(t * om) / Math.sin(om))); };
  data.links.forEach((l, i) => {
    const hq = data.hq[l.publisher], to = data.countries[l.country]; if (!hq || !to) return;
    const A = vec(hq[0], hq[1], 1.0), B = vec(to[0], to[1], 1.0);
    const ang = A.angleTo(B), h = .12 + .42 * ang / Math.PI;
    const c1 = slerpPt(A, B, .25).multiplyScalar(1 + h), c2 = slerpPt(A, B, .75).multiplyScalar(1 + h);
    const curve = new THREE.CubicBezierCurve3(A.clone().multiplyScalar(1.003), c1, c2, B.clone().multiplyScalar(1.003));
    const w = l.activities / maxLink;
    const geo = new THREE.TubeGeometry(curve, 96, .0022 + .0048 * w, 6, false);
    const mat = new THREE.ShaderMaterial({
      uniforms: {uHead: {value: -1}, uC: {value: new THREE.Color(PUB[l.publisher] || '#9CCBFF')}, uBase: {value: .10}, uDim: {value: 1}},
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      vertexShader: `varying float vU;void main(){vU=uv.x;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}`,
      fragmentShader: `uniform float uHead;uniform vec3 uC;uniform float uBase;uniform float uDim;varying float vU;
        void main(){float tail=.32;float k=clamp((vU-(uHead-tail))/tail,0.,1.)*step(vU,uHead);float head=smoothstep(uHead-.03,uHead,vU)*step(vU,uHead);
        float shown=step(vU,max(uHead,0.));float a=clamp((uBase*shown+pow(k,2.2)*.9+head*.6)*uDim,0.,1.);gl_FragColor=vec4(mix(uC,vec3(1.),head*.35)*a,a);}`
    });
    const mesh = new THREE.Mesh(geo, mat); globe.add(mesh);
    arcs.push({mesh, mat, l, country: names.indexOf(l.country) + 1, B, period: 4.2 + (i % 5) * .35, offset: (i * .61) % 4.2, hit: false, w});
  });

  // ---------- ripples at arrival ----------
  const ringGeo = new THREE.RingGeometry(.86, 1, 64);
  const ripples = [];
  function ripple(pos, color, w) {
    const m = new THREE.Mesh(ringGeo, new THREE.MeshBasicMaterial({color, transparent: true, opacity: .9, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide}));
    m.position.copy(pos).multiplyScalar(1.004); m.lookAt(pos.clone().multiplyScalar(2)); globe.add(m);
    ripples.push({m, t: 0, s: .035 + .05 * w});
  }

  // ---------- HQ beacons ----------
  const beaconTex = (() => { const c = document.createElement('canvas'); c.width = c.height = 128; const x = c.getContext('2d'); const g = x.createRadialGradient(64, 64, 0, 64, 64, 64); g.addColorStop(0, 'rgba(255,255,255,1)'); g.addColorStop(.18, 'rgba(255,255,255,.85)'); g.addColorStop(.4, 'rgba(255,255,255,.18)'); g.addColorStop(1, 'rgba(255,255,255,0)'); x.fillStyle = g; x.fillRect(0, 0, 128, 128); return new THREE.CanvasTexture(c); })();
  const beacons = Object.entries(data.hq).map(([p, ll]) => {
    const s = new THREE.Sprite(new THREE.SpriteMaterial({map: beaconTex, color: PUB[p], transparent: true, blending: THREE.AdditiveBlending, depthWrite: false}));
    s.position.copy(vec(ll[0], ll[1], 1.01)); s.scale.setScalar(.09); globe.add(s); return {s, p, pos: vec(ll[0], ll[1], 1)};
  });

  // ---------- post: bloom ----------
  const composer = new EffectComposer(renderer);
  composer.addPass(new RenderPass(scene, camera));
  const bloom = new UnrealBloomPass(new THREE.Vector2(1, 1), .7, .35, .32);
  composer.addPass(bloom); composer.addPass(new OutputPass());

  // ---------- layout: solved from measured text boxes, never hard-coded ----------
  // The globe disc (radius R_HIT, slightly beyond the land so the inner halo counts) must keep `gap` px clear of the
  // avoided element. Desktop: globe goes right of the text, centred in the free band, may bleed off the right edge by
  // at most 35% of its radius; if it still does not fit, the camera backs off (globe shrinks). Stacked (text spans the
  // width): globe goes above the text, may bleed off the top by 30% of its radius.
  const R_HIT = 1.05, FOV = 38;
  let W = 1, H = 1, rest = {x: .9, y: 0, z: 4.1}, place = rest, avoidEl = null;
  const fpx = () => (H / 2) / Math.tan(FOV * deg / 2);
  const rpx = z => fpx() * R_HIT / Math.sqrt(z * z - R_HIT * R_HIT);
  function solve(rect, zStart) {
    const f = fpx();
    const out = (cx, cy, z) => ({x: (cx - W / 2) * z / f, y: (H / 2 - cy) * z / f, z, cx, cy, r: rpx(z), mode: ''});
    if (!rect) return out(W * .62, topInset + (H - topInset) / 2, zStart);
    const stacked = rect.right > W * .62;
    for (let z = zStart; z < 14; z += .05) {
      const r = rpx(z);
      if (stacked) {
        if (2 * r > W * 1.05) continue;
        const cy = Math.min(rect.top - gap - r, topInset + (rect.top - gap - topInset) / 2);
        if (cy - r < topInset - .3 * r) continue;
        return Object.assign(out(W / 2, cy, z), {mode: 'stacked'});
      }
      if (2 * r > (H - topInset) * 1.04) continue;
      const left = rect.right + gap, band = W - left;
      const cx = band >= 2 * r ? left + band / 2 : left + r;
      if (cx + r > W + .35 * r) continue;
      return Object.assign(out(cx, topInset + (H - topInset) / 2, z), {mode: 'side'});
    }
    return Object.assign(out(W * .75, H / 2, 14), {mode: 'fallback'});
  }
  function relayout() {
    let heroRect = null;
    if (avoid) { const b = avoid.getBoundingClientRect(); heroRect = {left: b.left, right: b.right, top: b.top + scrollY, bottom: b.bottom + scrollY}; }
    rest = solve(heroRect, W < 760 ? 5.2 : 3.9);
    // avoidEl may be an element or a function returning the rect the element will occupy once it settles
    place = focus && avoidEl ? solve(typeof avoidEl === 'function' ? avoidEl() : avoidEl.getBoundingClientRect(), rest.z * .86) : rest;
    tgt.z = place.z;
  }
  function resize() {
    const r = canvas.getBoundingClientRect(); W = r.width; H = r.height;
    renderer.setSize(W, H, false); composer.setSize(W, H);
    camera.aspect = W / H; camera.updateProjectionMatrix();
    landMat.uniforms.uScale.value = W < 760 ? .8 : 1;
    relayout();
  }
  addEventListener('resize', resize);
  if (window.ResizeObserver && avoid) new ResizeObserver(() => relayout()).observe(avoid);
  document.fonts && document.fonts.ready.then(() => relayout());

  // ---------- rotation control: ease 6% per frame toward target (GitHub) ----------
  const rot = {x: 15 * deg, y: RM ? -30 * deg : 95 * deg}, tgt = {x: 15 * deg, y: -30 * deg, z: 4, ox: 0};
  let focus = 0, focusAmt = 0;
  resize();
  let auto = !RM, dragging = null, lastInteract = 0;
  canvas.addEventListener('pointerdown', e => { dragging = {x: e.clientX, y: e.clientY}; canvas.setPointerCapture(e.pointerId); lastInteract = performance.now(); });
  canvas.addEventListener('pointermove', e => { if (!dragging) return; tgt.y += (e.clientX - dragging.x) * .006; tgt.x = THREE.MathUtils.clamp(tgt.x + (e.clientY - dragging.y) * .004, -.9, .9); dragging = {x: e.clientX, y: e.clientY}; lastInteract = performance.now(); });
  addEventListener('pointerup', () => { dragging = null; });

  // ---------- focus API (scroll story) ----------
  function setFocus(country, el) {
    avoidEl = el || null;
    if (!country) { focus = 0; relayout(); auto = !RM; return; }
    const ll = data.countries[country]; focus = names.indexOf(country) + 1; auto = false;
    tgt.x = ll[0] * deg * .85; tgt.y = -ll[1] * deg; while (tgt.y - rot.y > Math.PI) tgt.y -= 2 * Math.PI; while (rot.y - tgt.y > Math.PI) tgt.y += 2 * Math.PI;
    relayout();
  }

  // ---------- labels ----------
  const labels = [];
  function label(text, cls) { const d = document.createElement('div'); d.className = 'glabel ' + (cls || ''); d.innerHTML = text; labelsEl.appendChild(d); return d; }
  const countryLabel = label('', 'country');
  const hqLabels = beacons.map(b => ({b, el: label(`<i style="background:${PUB[b.p]}"></i>${b.p}`, 'hq')}));
  const proj = new THREE.Vector3(), nrm = new THREE.Vector3(), camDir = new THREE.Vector3();
  function placeLabel(el, local, show) {
    proj.copy(local); globe.localToWorld(proj);
    nrm.copy(proj).sub(world.position).normalize(); camDir.copy(camera.position).sub(proj).normalize();
    const vis = show && nrm.dot(camDir) > .15;
    proj.project(camera);
    el.style.transform = `translate(${(proj.x * .5 + .5) * W}px,${(-proj.y * .5 + .5) * H}px)`;
    el.style.opacity = vis ? 1 : 0;
  }

  // ---------- quality tiers (GitHub: step down under ~55 fps) ----------
  let frames = 0, acc = 0, tier = 0;
  function tierCheck(dt) {
    if (tier >= 2) return; frames++; acc += dt;
    if (frames === 90) { const fps = 90 / acc; frames = 0; acc = 0;
      if (fps < 48) { tier++; if (tier === 1) { DPR = Math.min(DPR, 1.25); } else { DPR = 1; bloom.strength = .45; } renderer.setPixelRatio(DPR); landMat.uniforms.uDpr.value = DPR; resize(); } }
  }

  // ---------- loop ----------
  const clock = new THREE.Clock(); let t0 = null, visible = true, active = true;
  new IntersectionObserver(es => { visible = es[0].isIntersecting; }).observe(canvas);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) clock.getDelta(); });
  function frame() {
    requestAnimationFrame(frame);
    if (!visible || !active || document.hidden) return;
    const dt = Math.min(clock.getDelta(), .05), t = clock.elapsedTime; if (t0 === null) t0 = t;
    const since = t - t0;
    tierCheck(dt);
    // intro fly-in
    if (!RM) { const k = Math.min(since / 2.8, 1), e = 1 - Math.pow(1 - k, 4); landMat.uniforms.uReveal.value = Math.min(since / 2.2, 1); if (k < 1) { camera.position.z = 10 + (tgt.z - 10) * e; } }
    if (auto && !dragging && performance.now() - lastInteract > 2500) tgt.y -= dt * .05;
    rot.x += (tgt.x - rot.x) * .06; rot.y += (tgt.y - rot.y) * .06;
    globe.rotation.set(rot.x, rot.y, 0);
    if (RM || since > 2.8) camera.position.z += (tgt.z - camera.position.z) * .06;
    world.position.x += (place.x - world.position.x) * .08; world.position.y += (place.y - world.position.y) * .08;
    stars.rotation.y = rot.y * .08; stars.rotation.x = rot.x * .05;
    stars.material.uniforms.uTime.value = t; landMat.uniforms.uTime.value = t;
    focusAmt += ((focus ? 1 : 0) - focusAmt) * .06; landMat.uniforms.uFocus.value = focus; landMat.uniforms.uFocusAmt.value = focusAmt;
    // arcs
    const arcStart = RM ? -1e9 : 1.0;
    for (const a of arcs) {
      if (RM) { a.mat.uniforms.uHead.value = 1.0; a.mat.uniforms.uBase.value = .35; continue; }
      if (since < arcStart) { a.mat.uniforms.uHead.value = -1; continue; }
      const ph = ((since - arcStart + a.offset) % a.period) / a.period;   // 0..1
      const head = ph * 1.45;                                               // overshoot so the tail leaves
      a.mat.uniforms.uHead.value = head;
      const isF = focus && a.country === focus;
      a.mat.uniforms.uDim.value += (((focus ? (isF ? 1.6 : .18) : 1)) - a.mat.uniforms.uDim.value) * .08;
      a.mat.uniforms.uBase.value = isF ? .4 : .1;
      if (head >= 1 && !a.hit) { a.hit = true; if (!focus || isF) ripple(a.B, PUB[a.l.publisher], a.w); }
      if (head < 1) a.hit = false;
    }
    for (let i = ripples.length - 1; i >= 0; i--) { const r = ripples[i]; r.t += dt / 1.6; const s = r.s * (.2 + r.t * 1.1); r.m.scale.setScalar(s); r.m.material.opacity = .9 * (1 - r.t) * (1 - r.t); if (r.t >= 1) { globe.remove(r.m); r.m.material.dispose(); ripples.splice(i, 1); } }
    beacons.forEach((b, i) => b.s.scale.setScalar(.075 + .02 * Math.sin(t * 2 + i)));
    // labels
    const showHQ = !focus && (RM || since > 2.4);
    hqLabels.forEach(h => placeLabel(h.el, h.b.pos.clone().multiplyScalar(1.02), showHQ));
    if (focus) { const c = names[focus - 1]; countryLabel.textContent = c; placeLabel(countryLabel, vec(...data.countries[c], 1.02), true); } else countryLabel.style.opacity = 0;
    composer.render();
  }
  frame();
  onReady && onReady();
  // layout() reports the solved target circle in viewport px, for the layout guardrail check (web/globe/ui_layout_check.mjs)
  return {setFocus, relayout, layout: () => ({...place, w: W, h: H}), setActive(on) { if (on && !active) clock.getDelta(); active = on; }};
}
