// terminal.ts — minimal DOM terminal renderer (no framework).

export class Terminal {
  private el: HTMLElement;
  private streamingLine: HTMLElement | null = null;

  constructor(container: HTMLElement) {
    this.el = container;
  }

  private line(cls: string, text: string): HTMLElement {
    const div = document.createElement("div");
    div.className = cls;
    div.textContent = text;
    this.el.appendChild(div);
    this.el.scrollTop = this.el.scrollHeight;
    return div;
  }

  echo(text: string): void { this.line("cmd-echo", text); }
  out(text: string, isError = false): void { this.line(isError ? "out err" : "out", text); }
  meta(text: string): void { this.line("meta", text); }
  banner(text: string): void { this.line("banner", text); }
  clear(): void { this.el.innerHTML = ""; }

  // streaming AI: append tokens into one growing line
  beginStream(): void {
    this.streamingLine = this.line("out stream", "");
  }
  appendStream(text: string): void {
    if (!this.streamingLine) this.beginStream();
    this.streamingLine!.textContent += text;
    this.el.scrollTop = this.el.scrollHeight;
  }
  endStream(): void { this.streamingLine = null; }
}
