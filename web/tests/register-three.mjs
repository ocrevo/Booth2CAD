// Node has no import map: resolve the bare specifier 'three' (used by the browser modules) to the vendored copy.
import { registerHooks } from 'node:module';

const three = new URL('../app/vendor/three/three.module.js', import.meta.url).href;
registerHooks({
  resolve(specifier, context, nextResolve) {
    if (specifier === 'three') return { url: three, shortCircuit: true };
    return nextResolve(specifier, context);
  },
});
