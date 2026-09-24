import React from 'react';
import {
  AbsoluteFill,
  Audio,
  Easing,
  Img,
  OffthreadVideo,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from 'remotion';
import { useFontsReady } from './useFontsReady';

/**
 * Composites the Manim scenes over the brand frame and adds the karaoke captions.
 *
 * Division of labour (ported from aiducation-ielts ManimLesson): Manim drew the
 * animation and knows nothing about the lesson; this owns the cream ground, grain,
 * wordmark, captions and audio. Everything is resolved in run.py and passed as props,
 * so every frame is a pure function of `frame`.
 */

const theme = {
  paper: '#F5EFE2',
  paperEdge: '#EBE3D1',
  ink: '#1C1C1A',
  inkMuted: '#57554E',
  inkFaint: '#A6A196',
  jade: '#1F6F5C',
  jadeSoft: '#D3E3DA',
  font: '"Be Vietnam Pro", sans-serif',
};

export type Word = { text: string; from: number; to: number };
export type Caption = { from: number; durationInFrames: number; words: Word[] };
export type Background = { src: string; zoom?: 'in' | 'out' | 'none'; wash?: number };
export type SlideState = { src: string; from: number };
export type SlideReveal = { src: string; box: [number, number, number, number]; from: number; anim?: string };
export type Shot = {
  kind?: 'clip' | 'slide';
  src?: string;
  from: number;
  durationInFrames: number;
  background?: Background;
  states?: SlideState[];
  reveals?: SlideReveal[];
};
export type LessonProps = {
  fps: number;
  width: number;
  height: number;
  durationInFrames: number;
  subject: string;
  audio: string | null;
  shots: Shot[];
  captions: Caption[];
  captions_mode?: 'on' | 'overlay' | 'off';
};

/** Deck pages are 1920x1080 artwork; with captions on they shrink to leave a strip. */
const SLIDE_SCALE_WITH_CAPTIONS = 0.82;
const REVEAL_FRAMES = 33; // 0.55 s at 60 fps — vox-director's measured fly-in

export const Lesson: React.FC<LessonProps> = (p) => {
  useFontsReady();
  // Pixels, not %: CSS resolves vertical % padding against WIDTH, which would drop
  // the caption back under TikTok's own caption/CTA stack.
  const vertical = p.height > p.width;
  const mode = p.captions_mode ?? 'on';
  const slideScale = !vertical && mode === 'on' ? SLIDE_SCALE_WITH_CAPTIONS : 1;
  const inset = Math.round(p.height * (vertical ? 0.2 : 0.03));

  return (
    <AbsoluteFill style={{ background: theme.paper }}>
      <Grain />
      {p.shots.map((s, i) => (
        <Sequence key={i} from={s.from} durationInFrames={s.durationInFrames}>
          {s.background ? <BackgroundImage bg={s.background} duration={s.durationInFrames} /> : null}
          {s.kind === 'slide' ? (
            <SlideShot shot={s} width={p.width} height={p.height} scale={slideScale} />
          ) : (
            /* `transparent` is not optional: without it the clip is an opaque rectangle.
               Wrapped in AbsoluteFill so it stacks above a background image (a
               positioned sibling would otherwise paint over an in-flow video). */
            <AbsoluteFill>
              <OffthreadVideo src={staticFile(s.src!)} transparent />
            </AbsoluteFill>
          )}
        </Sequence>
      ))}
      {mode === 'off'
        ? null
        : p.captions.map((c, i) => (
            <Sequence key={i} from={c.from} durationInFrames={c.durationInFrames}>
              <Karaoke caption={c} inset={inset} compact={!vertical} />
            </Sequence>
          ))}
      <Wordmark subject={p.subject} />
      {p.audio ? <Audio src={staticFile(p.audio)} /> : null}
    </AbsoluteFill>
  );
};

/**
 * The line being spoken, word by word. Word times are frames relative to the line's
 * start, measured from the actual audio by the local aligner, not estimated.
 * Spoken words are ink, the current word sits on a jade pill, upcoming words wait in
 * a faint tone so the viewer can read ahead.
 */
const Karaoke: React.FC<{ caption: Caption; inset: number; compact?: boolean }> = ({ caption, inset, compact }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(
    frame,
    [0, 5, caption.durationInFrames - 5, caption.durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }
  );

  return (
    <AbsoluteFill
      style={{
        justifyContent: 'flex-end',
        alignItems: 'center',
        paddingBottom: inset,
        paddingLeft: compact ? 90 : 70,
        paddingRight: compact ? 90 : 70,
      }}
    >
      <div
        style={{
          opacity,
          // A flex child sizes to its content and would run off both edges; cap it so
          // long lines wrap inside the safe width.
          maxWidth: '100%',
          boxSizing: 'border-box',
          fontFamily: theme.font,
          fontWeight: 600,
          fontSize: compact ? 36 : 44,
          lineHeight: 1.45,
          textAlign: 'center',
          background: theme.paperEdge,
          padding: compact ? '12px 22px' : '18px 26px',
          borderRadius: 12,
        }}
      >
        {page(caption.words, frame, compact ? 18 : 14).map((w, i) => {
          const current = frame >= w.from && frame < w.to;
          const spoken = frame >= w.to;
          return (
            <span
              key={i}
              style={{
                color: current ? theme.paper : spoken ? theme.ink : theme.inkFaint,
                background: current ? theme.jade : 'transparent',
                borderRadius: 8,
                padding: '0 6px',
                margin: '0 1px',
                display: 'inline-block',
              }}
            >
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/**
 * A deck page. `states[k]` is the page with the first k elements present (exact
 * renders for vector PDFs). While element k flies in, the previous state shows under
 * its cut-out sprite; when it lands, the next state takes over — so the resting
 * frame is always the author's own pixels.
 */
const SlideShot: React.FC<{ shot: Shot; width: number; height: number; scale: number }> = ({ shot, width, height, scale }) => {
  const frame = useCurrentFrame();
  const states = shot.states ?? [];
  const current = [...states].reverse().find((s) => frame >= s.from) ?? states[0];
  const w = 1920 * scale * (width / 1920);
  const h = 1080 * scale * (width / 1920);
  const left = (width - w) / 2;
  const top = scale < 1 ? Math.round(height * 0.02) : (height - h) / 2;
  const k = w / 1920;
  return (
    <AbsoluteFill>
      <div style={{ position: 'absolute', left, top, width: w, height: h, overflow: 'hidden', borderRadius: scale < 1 ? 14 : 0 }}>
        {current ? <Img src={staticFile(current.src)} style={{ width: '100%', height: '100%' }} /> : null}
        {(shot.reveals ?? []).map((r, i) => {
          const t = frame - r.from;
          if (t < 0 || t >= REVEAL_FRAMES) return null;
          const p = interpolate(t, [0, REVEAL_FRAMES], [0, 1], { easing: Easing.out(Easing.cubic) });
          const [x0, y0, x1, y1] = r.box;
          const travel = 140; // capped, not proportional: a wide title sliding its own width reads as a swipe
          let dx = 0, dy = 0, sc = 1;
          switch (r.anim) {
            case 'left': dx = -travel * (1 - p); break;
            case 'right': dx = travel * (1 - p); break;
            case 'drop': dy = -travel * (1 - p); break;
            case 'pop': sc = 0.82 + 0.18 * p; break;
            case 'fade': break;
            default: dy = 28 * (1 - p); sc = 0.97 + 0.03 * p; // rise
          }
          return (
            <Img
              key={i}
              src={staticFile(r.src)}
              style={{
                position: 'absolute', left: x0 * k, top: y0 * k, width: (x1 - x0) * k, height: (y1 - y0) * k,
                opacity: Math.min(1, p * 1.6), transform: `translate(${dx * k}px, ${dy * k}px) scale(${sc})`,
              }}
            />
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/** A photo behind a lesson scene: slow push (Ken Burns) under a cream wash for legibility. */
const BackgroundImage: React.FC<{ bg: Background; duration: number }> = ({ bg, duration }) => {
  const frame = useCurrentFrame();
  const z = bg.zoom ?? 'in';
  const s = z === 'none' ? 1 : interpolate(frame, [0, duration], z === 'in' ? [1.0, 1.08] : [1.08, 1.0]);
  return (
    <AbsoluteFill>
      <Img src={staticFile(bg.src)} style={{ width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${s})` }} />
      <AbsoluteFill style={{ background: theme.paper, opacity: bg.wash ?? 0.72 }} />
    </AbsoluteFill>
  );
};

/**
 * Long lines are shown a page at a time (about two caption lines), so a 200-character
 * sentence never grows a third line up into the picture. The page is whichever one
 * holds the word being spoken; pages break at word boundaries, preferring punctuation.
 */
function page(words: Word[], frame: number, max: number): Word[] {
  if (words.length <= max) return words;
  const pages: Word[][] = [];
  let cur: Word[] = [];
  for (const w of words) {
    cur.push(w);
    const soft = cur.length >= max * 0.6 && /[,.;:!?]$/.test(w.text);
    if (cur.length >= max || soft) {
      pages.push(cur);
      cur = [];
    }
  }
  if (cur.length) pages.push(cur);
  const idx = pages.findIndex((p) => frame < p[p.length - 1].to);
  return pages[idx === -1 ? pages.length - 1 : idx];
}

const Wordmark: React.FC<{ subject: string }> = ({ subject }) => (
  <div
    style={{
      position: 'absolute',
      right: 44,
      top: 34,
      fontFamily: theme.font,
      fontWeight: 700,
      fontSize: 22,
      letterSpacing: 1.5,
      color: theme.inkMuted,
      opacity: 0.75,
    }}
  >
    <span style={{ color: theme.jade }}>AIDUCATION</span>
    {subject ? ` · ${subject}` : ''}
  </div>
);

/** Fine even tooth over the page; inline SVG so it cannot 404 mid-render. */
const Grain: React.FC = () => (
  <AbsoluteFill
    style={{
      opacity: 0.16,
      mixBlendMode: 'multiply',
      backgroundImage:
        "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='120' height='120'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='3'/></filter><rect width='120' height='120' filter='url(%23n)' opacity='0.5'/></svg>\")",
    }}
  />
);
