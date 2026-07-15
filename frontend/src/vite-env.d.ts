/// <reference types="vite/client" />
// Minimal fallback so type-checking works even before `npm install`.
interface ImportMeta {
  readonly env: {
    readonly VITE_API_BASE?: string;
    readonly [key: string]: string | undefined;
  };
}
