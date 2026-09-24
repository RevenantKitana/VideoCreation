import { Config } from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
// Flat vector frames compress hard; CRF 20 is visually lossless here.
Config.setCrf(20);
// Use EGL on Linux for headless GPU rendering (Nvidia T4), angle on Windows/Mac
if (process.platform === 'linux') {
  Config.setChromiumOpenGlRenderer('egl');
} else {
  Config.setChromiumOpenGlRenderer('angle');
}
