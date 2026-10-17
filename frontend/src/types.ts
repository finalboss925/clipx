export type Brand = {
  name: string;
  font: "DejaVu Sans" | "Liberation Sans" | "Arial";
  color: string;
  text_color: string;
  logo: string | null;
  intro: string | null;
  outro: string | null;
  emoji: string;
};
export type Options = {
  min_length: number;
  max_length: number;
  clip_count: number;
  aspect: string;
  caption_style: string;
  language: string;
  cleanup: boolean;
  layout: string;
  provider: string;
  transcription: string;
  brand: Brand;
};
export type Job = {
  id: string;
  project_id: string;
  kind: string;
  status: string;
  stage: string;
  progress: number;
  error: string | null;
  clip_id: string | null;
};
export type Clip = {
  id: string;
  project_id: string;
  title: string;
  start: number;
  end: number;
  total: number;
  hook: string;
  reason: string;
  scores: Record<string, number>;
  description: string;
  hashtags: string[];
  caption_style: string;
  offset: number;
  deleted_words: number[];
  video_url: string | null;
  thumbnail_url: string | null;
  srt_url: string | null;
  render_id: string | null;
};
export type Project = {
  id: string;
  title: string;
  status: string;
  duration: number;
  created_at: string;
  options: Options;
  jobs: Job[];
  clips: Clip[];
  poster_url: string;
  cost: { estimated_usd: number; basis: string };
};
export type Word = { index: number; start: number; end: number; text: string };
export const defaults: Options = {
  min_length: 15,
  max_length: 60,
  clip_count: 5,
  aspect: "9:16",
  caption_style: "karaoke",
  language: "auto",
  cleanup: false,
  layout: "face",
  provider: "local",
  transcription: "local",
  brand: {
    name: "My brand",
    font: "DejaVu Sans",
    color: "#B4F16F",
    text_color: "#FFFFFF",
    logo: null,
    intro: null,
    outro: null,
    emoji: "",
  },
};
export const styles = ["karaoke", "bold", "minimal", "neon", "boxed"];
export const time = (s: number) =>
  `${Math.floor(s / 60)}:${Math.floor(s % 60)
    .toString()
    .padStart(2, "0")}`;
export async function api<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch("/api" + url, init);
  if (!r.ok) {
    let detail = "";
    try {
      detail = (await r.json()).detail;
    } catch {}
    throw new Error(
      typeof detail === "string" ? detail : `Request failed (${r.status})`,
    );
  }
  return r.json();
}
