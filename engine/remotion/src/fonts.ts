import { loadFont } from '@remotion/fonts';
import { staticFile } from 'remotion';

/**
 * Self-hosted only. A Google Fonts <link> races the renderer and yields a handful of
 * frames with fallback metrics — a flicker that appears only in the output file and
 * never in the studio preview.
 *
 * Lazy on purpose. `loadFont()` opens its own delayRender handle internally, so calling
 * it at module scope opens one while Remotion is merely enumerating compositions —
 * before any frame has been asked for, and once per renderer tab under `--concurrency`.
 * Those handles time out and kill the render. Called from a component instead, via
 * useFontsReady, the handle opens and closes inside a real frame's lifecycle.
 */
let promise: Promise<unknown> | null = null;

export function loadFonts(): Promise<unknown> {
  if (!promise) {
    promise = Promise.all([
      loadFont({ family: 'Be Vietnam Pro', url: staticFile('fonts/BeVietnamPro-Regular.ttf'), weight: '400' }),
      loadFont({ family: 'Be Vietnam Pro', url: staticFile('fonts/BeVietnamPro-SemiBold.ttf'), weight: '600' }),
      loadFont({ family: 'Be Vietnam Pro', url: staticFile('fonts/BeVietnamPro-Bold.ttf'), weight: '700' }),
    ]);
  }
  return promise;
}
