# DX Agent Dev

A natural-language console for building DEEPX NPU apps: describe what you want, and a
coding agent generates and runs it. It is also a chat assistant and a gallery of
ready-made showcases.

![DX Agent Dev — the agent console (agent / model / target), the build prompt, and the showcase gallery.](../resources/agent.png)

## Using it

1. **Connect an agent** — the console detects installed coding CLIs (e.g. Claude,
   Cursor). A badge shows whether each is signed in; if a login is needed it shows the
   exact command to run, then re-checks.
2. **Set the run** — choose the **target** (which repo the agent works in: Suite,
   dx-runtime, dx_app, dx_stream, dx-compiler), the **interaction mode** (Interactive vs
   Autopilot), and the **reasoning effort**. A hint warns if the chosen model is too weak
   and suggests a stronger one.
3. **Describe your task** in the prompt — the agent works and streams its progress live;
   an expandable **activity panel** shows each turn's shell / tool output next to the reply.
4. **Chat** — ask questions in the assistant; besides the coding agents you can point it
   at a **local LLM** (Ollama / vLLM / LM Studio — any OpenAI-compatible endpoint) or use
   a signed-in coding CLI as the chat backend.
5. **Showcases** — browse the gallery of example NPU apps for reference.

## Key features

- **Bring-your-own agent** — uses whatever coding CLI you have installed and signed in;
  one login powers both the generator and the chat.
- **Local / self-hosted LLM** support (any OpenAI-compatible endpoint; auto-discovers
  models). No API key is stored — it is just an HTTP client.
- **SDK knowledge** — the assistant can pull in DEEPX SDK documentation to answer
  accurately, with a refresh button to update it.
- **Live streaming** of the agent's work, with a wall-clock timeout so a stuck run frees
  the slot for the next request.
