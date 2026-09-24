import React from 'react';
import { Composition } from 'remotion';
import { Lesson, type LessonProps } from './Lesson';

/**
 * One composition. Everything about a video (length, clips, captions, audio) arrives
 * as --props from run.py, so this file never changes per video.
 */
const empty: LessonProps = {
  fps: 60, width: 1080, height: 1920, durationInFrames: 60,
  subject: '', audio: null, shots: [], captions: [],
};

export const Root: React.FC = () => (
  <Composition
    id="Lesson"
    component={Lesson}
    defaultProps={empty}
    durationInFrames={60}
    fps={60}
    width={1080}
    height={1920}
    calculateMetadata={({ props }) => ({
      durationInFrames: props.durationInFrames,
      fps: props.fps,
      width: props.width,
      height: props.height,
    })}
  />
);
