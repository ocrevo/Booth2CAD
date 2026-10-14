// Spec camera -> three.js camera ("match source view"). Same convention as booth-image-to-model/scripts/camera_math.py:
// the camera looks from `position` to `target` with Z up, `roll_deg` turns it about its view axis, the lens is fitted to
// the sensor WIDTH, and `principal_point` is normalised with v pointing down. projectPoint() is a port of camera_math.project
// so a test can check the three.js camera lands points on the same pixels as the Python code.

const rad = (d) => (d * Math.PI) / 180;
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const unit = (a) => {
  const n = Math.sqrt(dot(a, a));
  if (!Number.isFinite(n) || n < 1e-12) throw new Error('degenerate vector');
  return a.map((v) => v / n);
};

/** [forward, right, up] unit vectors in world space (roll included). */
export function cameraAxes(cam) {
  const fwd = unit(sub(cam.target, cam.position));
  if (Math.abs(fwd[2]) > 1 - 1e-9) throw new Error('camera looks straight up/down; roll is undefined');
  const right = unit(cross(fwd, [0, 0, 1]));
  const up = cross(right, fwd);
  const r = rad(cam.roll_deg || 0);
  const [c, s] = [Math.cos(r), Math.sin(r)];
  return [fwd, right.map((v, i) => c * v + s * up[i]), up.map((v, i) => c * v - s * right[i])];
}

export function focalPx(cam, width) {
  if ((cam.projection || 'perspective') !== 'perspective') throw new Error('only perspective cameras are supported');
  return (cam.lens_mm / cam.sensor_width_mm) * width;
}

/** World point -> [u_px, v_px, depth] on a width x height canvas (origin top-left). */
export function projectPoint(point, cam, width, height) {
  const [fwd, right, up] = cameraAxes(cam);
  const d = sub(point, cam.position);
  const z = dot(d, fwd);
  if (z <= 1e-9) throw new Error('point is behind the camera');
  const f = focalPx(cam, width);
  const pp = cam.principal_point || [0.5, 0.5];
  return [pp[0] * width + (f * dot(d, right)) / z, pp[1] * height - (f * dot(d, up)) / z, z];
}

/** The largest rectangle with the source aspect that fits the viewport, centred (what "match source view" shows). */
export function frameRect(source, viewport) {
  const s = Math.min(viewport.width / source.width, viewport.height / source.height);
  const w = source.width * s;
  const h = source.height * s;
  return { x: (viewport.width - w) / 2, y: (viewport.height - h) / 2, width: w, height: h, scale: s };
}

/**
 * Point a three.js PerspectiveCamera the way the spec camera looks at the source image.
 * `source` = { width, height } of the original picture, `viewport` = { width, height } of the canvas.
 * Returns the frame rectangle (in viewport pixels) that corresponds to the source picture.
 */
export function applySpecCamera(camera, cam, source, viewport) {
  const [fwd, , up] = cameraAxes(cam);
  const frame = frameRect(source, viewport);
  const halfTan = cam.sensor_width_mm / (2 * cam.lens_mm);                 // tan(horizontal fov / 2), sensor fit = width
  const aspectViewport = viewport.width / viewport.height;
  camera.fov = (2 * Math.atan(halfTan / Math.min(source.width / source.height, aspectViewport)) * 180) / Math.PI;
  camera.aspect = aspectViewport;
  camera.position.set(...cam.position);
  camera.up.set(...up);
  camera.lookAt(...cam.target);
  const pp = cam.principal_point || [0.5, 0.5];
  if (Math.abs(pp[0] - 0.5) > 1e-9 || Math.abs(pp[1] - 0.5) > 1e-9) {
    camera.setViewOffset(viewport.width, viewport.height, (0.5 - pp[0]) * frame.width, (0.5 - pp[1]) * frame.height, viewport.width, viewport.height);
  } else camera.clearViewOffset();
  camera.updateProjectionMatrix();
  camera.updateMatrixWorld(true);
  return { frame, forward: fwd };
}
