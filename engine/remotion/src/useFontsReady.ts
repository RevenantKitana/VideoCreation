import { useEffect, useState } from 'react';
import { delayRender, continueRender } from 'remotion';
import { loadFonts } from './fonts';

/**
 * Holds the frame until the self-hosted faces are parsed.
 *
 * The handle is opened during RENDER (useState initialiser) and cleared in the effect.
 * Opening it in the effect instead would race the capture: Remotion only waits for
 * handles that already exist when it looks, and an effect can run after that check.
 *
 * This is the one place useState/useEffect is allowed. It gates WHETHER a frame is
 * captured, never WHAT the frame contains — nothing here is a function of time, so
 * out-of-order frame rendering stays deterministic.
 */
export function useFontsReady(): void {
  const [handle] = useState(() =>
    delayRender('load-fonts', { timeoutInMilliseconds: 60000 })
  );

  useEffect(() => {
    let done = false;
    const finish = () => {
      if (!done) {
        done = true;
        continueRender(handle);
      }
    };
    loadFonts()
      .catch((e) => console.error('[fonts] load failed, rendering with fallbacks', e))
      .finally(finish);
    return finish;
  }, [handle]);
}
