import { FormEvent, useEffect, useMemo, useState } from 'react';

type JobState = {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;
  message: string;
  download_url?: string;
};

function resolveApiBaseUrl(): string {
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL;
  }
  if (typeof window !== 'undefined') {
    return `${window.location.protocol}//${window.location.hostname}:8000`;
  }
  return 'http://localhost:8000';
}

const API_BASE_URL = resolveApiBaseUrl();

function formatNetworkError(error: unknown): string {
  if (error instanceof TypeError) {
    return `Backend nicht erreichbar unter ${API_BASE_URL}. Starte den FastAPI Server oder setze VITE_API_BASE_URL korrekt.`;
  }
  return error instanceof Error ? error.message : 'Unbekannter Netzwerkfehler';
}

export default function App() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [language, setLanguage] = useState<'de' | 'en'>('de');
  const [prompt, setPrompt] = useState('');
  const [error, setError] = useState('');
  const [job, setJob] = useState<JobState | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const canSubmit = useMemo(() => selectedFile && !isSubmitting, [selectedFile, isSubmitting]);

  useEffect(() => {
    if (!job || job.status === 'completed' || job.status === 'failed') {
      return;
    }

    const timer = window.setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/jobs/${job.job_id}`);
        if (!response.ok) {
          throw new Error(`Polling failed with status ${response.status}`);
        }
        const payload = (await response.json()) as JobState;
        setJob(payload);
      } catch (pollError) {
        setError(formatNetworkError(pollError));
      }
    }, 2000);

    return () => {
      window.clearInterval(timer);
    };
  }, [job]);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!selectedFile) {
      setError('Bitte waehle zuerst eine Videodatei aus.');
      return;
    }

    setError('');
    setIsSubmitting(true);
    setJob(null);

    try {
      const formData = new FormData();
      formData.append('file', selectedFile);
      formData.append('language', language);
      formData.append('user_prompt', prompt.trim());

      const response = await fetch(`${API_BASE_URL}/api/jobs`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) {
        let detail = `Upload failed with status ${response.status}`;
        try {
          const payload = (await response.json()) as { detail?: string };
          detail = payload.detail ?? detail;
        } catch {
          // Ignore JSON parse failures and keep fallback detail.
        }
        throw new Error(detail);
      }

      const payload = (await response.json()) as JobState;
      setJob(payload);
    } catch (submitError) {
      setError(formatNetworkError(submitError));
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="min-h-screen bg-zinc-950 text-zinc-100">
      <section className="mx-auto flex min-h-screen w-full max-w-5xl flex-col justify-center px-6 py-14">
        <p className="text-sm uppercase tracking-[0.24em] text-zinc-400">Automated AI Video Cutter</p>
        <h1 className="mt-3 text-4xl font-semibold tracking-tight text-white md:text-5xl">AI Video Cutter</h1>
        <p className="mt-4 max-w-2xl text-zinc-300">
          Upload, transkribieren, Highlights per LM Studio analysieren und das finale Video automatisch schneiden.
        </p>
        <p className="mt-2 text-sm text-zinc-400">API Endpoint: {API_BASE_URL}</p>

        <form
          onSubmit={handleSubmit}
          className="mt-10 space-y-6 rounded-xl border border-zinc-800 bg-zinc-900/70 p-6 backdrop-blur"
        >
          <div className="space-y-2">
            <label htmlFor="file" className="text-sm text-zinc-200">
              Video Upload
            </label>
            <input
              id="file"
              type="file"
              accept="video/*,.mkv,.avi,.mov,.mp4,.webm"
              onChange={(event) => setSelectedFile(event.target.files?.[0] ?? null)}
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm file:mr-4 file:rounded-md file:border-0 file:bg-zinc-700 file:px-3 file:py-2 file:text-sm file:text-zinc-100 hover:file:bg-zinc-600"
            />
          </div>

          <div className="space-y-2">
            <label htmlFor="language" className="text-sm text-zinc-200">
              Sprache
            </label>
            <select
              id="language"
              value={language}
              onChange={(event) => setLanguage(event.target.value as 'de' | 'en')}
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"
            >
              <option value="de">Deutsch</option>
              <option value="en">English</option>
            </select>
          </div>

          <div className="space-y-2">
            <label htmlFor="prompt" className="text-sm text-zinc-200">
              Optionaler Prompt
            </label>
            <textarea
              id="prompt"
              value={prompt}
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Wenn leer, wird automatisch 'Cut only the highlights.' verwendet."
              rows={4}
              className="w-full rounded-md border border-zinc-700 bg-zinc-950 px-3 py-2 text-sm"
            />
          </div>

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full rounded-md bg-blue-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-400 disabled:cursor-not-allowed disabled:bg-zinc-700"
          >
            {isSubmitting ? 'Upload laeuft...' : 'Upload starten'}
          </button>
        </form>

        {job && (
          <section className="mt-8 space-y-3 rounded-xl border border-zinc-800 bg-zinc-900/70 p-6">
            <div className="flex items-center justify-between text-sm text-zinc-300">
              <span>Status: {job.status}</span>
              <span>{job.progress}%</span>
            </div>
            <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-800">
              <div
                className="h-full bg-blue-500 transition-all duration-500"
                style={{ width: `${Math.max(2, job.progress)}%` }}
              />
            </div>
            <p className="text-sm text-zinc-300">{job.message}</p>
            {job.status === 'completed' && job.download_url && (
              <a
                href={`${API_BASE_URL}${job.download_url}`}
                className="inline-flex rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-400"
              >
                Ergebnis herunterladen
              </a>
            )}
          </section>
        )}

        {error && <p className="mt-6 rounded-md border border-red-500/50 bg-red-950/50 p-3 text-sm text-red-300">{error}</p>}
      </section>
    </main>
  );
}
