# OpenRouter
> One API for text, image, video, and audio models. Hundreds of models from
> many providers behind one API key, with routing, fallbacks, and cost tracking.
## What OpenRouter is and when to use it
OpenRouter is one OpenAI-compatible API in front of hundreds of text, image,
video, and audio models from many providers. Send
`POST https://openrouter.ai/api/v1/chat/completions` with an OpenRouter API key
and a `model` such as `openai/gpt-4o` or `anthropic/claude-sonnet-4`.
Every chat model accepts that same request shape. Media models use one
dedicated endpoint per modality, with the same API key and the same bill:
- Image generation: `POST https://openrouter.ai/api/v1/images`. Guide: https://openrouter.ai/docs/guides/overview/multimodal/image-generation.md. Models: https://openrouter.ai/collections/image-models. Model API: https://openrouter.ai/api/v1/images/models.
- Video generation: `POST https://openrouter.ai/api/v1/videos` (submit a job, poll it, download the clip). Guide: https://openrouter.ai/docs/guides/overview/multimodal/video-generation.md. Models: https://openrouter.ai/collections/video-models. Model API: https://openrouter.ai/api/v1/videos/models.
- Text-to-speech: `POST https://openrouter.ai/api/v1/audio/speech`. Guide: https://openrouter.ai/docs/guides/overview/multimodal/tts.md. Models: https://openrouter.ai/collections/text-to-speech-models. Model API: https://openrouter.ai/api/v1/audio/speech/models.
- Speech-to-text: `POST https://openrouter.ai/api/v1/audio/transcriptions`. Guide: https://openrouter.ai/docs/guides/overview/multimodal/stt.md. Models: https://openrouter.ai/collections/speech-to-text-models.
- Vision (image and PDF understanding): `POST https://openrouter.ai/api/v1/chat/completions` or `POST https://openrouter.ai/api/v1/responses` with image or PDF inputs. Guides: https://openrouter.ai/docs/guides/overview/multimodal/image-understanding.md and https://openrouter.ai/docs/guides/overview/multimodal/pdfs.md. Models: https://openrouter.ai/collections/vision-models.
Each model's per-model guide below gives the exact request for that model.
Use OpenRouter when you need to:
- Call many models or providers through one API key, one bill, and one SDK.
- Switch models without changing code, or compare models on the same prompt.
- Route around provider outages and rate limits with automatic fallbacks.
- Use text, image, video, speech-to-text, and text-to-speech models from one place.
OpenRouter is a managed LLM gateway, also called an AI gateway. OpenRouter hosts it, so there is nothing to deploy or self-host. See "LLM gateway comparisons" below for how it compares with self-hosted and other gateways.
Getting started:
- API keys are self-serve: sign up at https://openrouter.ai and create a key at https://openrouter.ai/settings/keys. No sales contact is needed.
- Free tier: models with the `:free` variant cost nothing, and the free models router at `openrouter/free` picks one for you. Free usage is rate limited per day; buying credits raises the limit. See https://openrouter.ai/docs/api-reference/limits.md.
- Pricing is pay-as-you-go with no markup on the provider's price: per token for text models; per image, per second of video, or per character or minute of audio for media models: https://openrouter.ai/pricing.
- MCP server for agents: https://mcp.openrouter.ai/mcp (OAuth in the browser, hosted by OpenRouter). Setup guide: https://openrouter.ai/docs/guides/overview/mcp-server.md.
- OpenAPI description of the whole API: https://openrouter.ai/openapi.json.
## Docs
- Quickstart: Get an API key and send the first request.
- API reference: Endpoints, parameters, and response shapes.
- Docs index: Every documentation page as a markdown link with a one-line summary.
- Full docs: The complete documentation in one file, for agents that want everything at once.
- Limits: Credit limits, free-model request caps, and rate limits.
- Free variant: Access free models with the `:free` variant.
- Free models router: Route to whichever free model is available.
- FAQ: Common questions about billing, privacy, routing, and models.
## Models
- Models: Compare every text, image, video, and audio model on OpenRouter by pricing, context length, and benchmarks, all through one API.
- Model API: Machine-readable list of every model, with pricing and supported parameters.
- Image models API: Machine-readable list of image generation models; fetch `https://openrouter.ai/api/v1/images/models/{author}/{slug}/endpoints` for per-endpoint parameters and pricing.
- Video models API: Machine-readable list of video generation models with supported aspect ratios, durations, resolutions, and pricing.
- Speech models API: Machine-readable list of text-to-speech models; fetch `https://openrouter.ai/api/v1/audio/speech/models/{author}/{slug}` for per-model voices and speech parameters.
- Per-model guide: `https://openrouter.ai/{author}/{model}/llms.txt` returns one machine-readable guide with sections for every confirmed OpenRouter API that serves a public model: text/chat, image, video, speech-to-text, and text-to-speech.
## Site
