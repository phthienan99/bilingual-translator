# Third-party components and model notices

The original v72 archive named MLX Whisper small.en, MLX Qwen2.5-3B-Instruct 4-bit, Marian English-to-Chinese, and NLLB English-to-Vietnamese.

This web candidate downloads the following models at runtime; weights are not included in the source or Docker build context:

- [Systran/faster-whisper-base.en](https://huggingface.co/Systran/faster-whisper-base.en) — default CPU speech recognition; small.en remains an optional larger alternative.
- [Qwen/Qwen2.5-0.5B-Instruct-GGUF](https://huggingface.co/Qwen/Qwen2.5-0.5B-Instruct-GGUF) — Apache-2.0, default English review, Q8_0 representation; tokenizer from Qwen/Qwen2.5-0.5B-Instruct.
- [Qwen/Qwen2.5-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-3B-Instruct) — optional larger review/Chinese mode, Q4_K_M from the official GGUF repository; Qwen research license.
- [Helsinki-NLP/opus-mt-en-zh](https://huggingface.co/Helsinki-NLP/opus-mt-en-zh) — Chinese translation fallback.
- [facebook/nllb-200-distilled-600M](https://huggingface.co/facebook/nllb-200-distilled-600M) — CC-BY-NC-4.0; Vietnamese translation. Upstream describes a research model, not a production translation service.

Software dependencies are listed in requirements.txt and retain their upstream licenses. Before redistributing a built image, review and retain the notices supplied by the installed packages. Before bundling model weights, review and retain each model's exact license and notices. No additional rights to third-party assets are granted by this project.

Original team code has no confirmed project-wide license in the provided source. Team agreement is still needed before selecting one. This package is an academic prototype.
