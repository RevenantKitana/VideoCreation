import { Config } from '@remotion/cli/config';

Config.setVideoImageFormat('jpeg');
Config.setOverwriteOutput(true);
// Flat vector frames compress hard; CRF 20 is visually lossless here.
Config.setCrf(20);
Config.setChromiumOpenGlRenderer('angle');
