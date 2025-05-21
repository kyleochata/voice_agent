# Project Wrap-Up

This challenge was a deep dive into real-time voice workflows and third-party API integration, all under an initial 4-hour timebox (later extended to 24 hours) as part of a take-home project for a job application. One of the biggest challenges was working within the free tier limits of OpenAI and ElevenLabs — both of which are extremely sensitive to timeouts and rate limits.

For future reference: navigate to the livekit folder in the LiveKit Python SDK `livekit.types.py` and modify the following:

```
@dataclass(frozen=True)
class APIConnectOptions:
    max_retry: int = 3
    """
    Maximum number of retries to connect to the API.
    """

    retry_interval: float = 10.0
    """
    Interval between retries to connect to the API in seconds.
    """

    timeout: float = 20.0 <== Change as needed
    """
    Timeout for connecting to the API in seconds.
    """
```
Note: when using Elevenlabs as the STT (speech-to-text) option, it will throw a `500: unusual behavior` error if the timeout is longer than 30 seconds.

### Why This Was a Big Deal
The `.llm` object seemed to ignore any custom timeout settings. The real blocker was that LiveKit silently enforces its own internal timeout via this `APIConnectOptions` class — and it's not mentioned anywhere in the official documentation or the LiveKit “Getting Started” materials.

The fix seems obvious in hindsight, but finding it took hours of trial, error, digging through the SDK source code, and debugging vague `NoneType` errors. I wasn’t going to pay for upgraded API tiers just to test my fix, so this hack was necessary to keep moving.

## What I’d Do Differently

- **Preload voice synthesis**: For known prompts, cache ElevenLabs outputs instead of generating them on-demand.
- **Implement a local fallback**: Use Whisper.cpp or llama.cpp to back up STT/LLM requests when APIs fail.
- **Add a Web UI**: A simple React dashboard could’ve helped visualize errors and logs in real time.
- **Add Testing**: I proritized speed and delivering a working end-to-end product that sacrificed modularity and testing to deliver something workable. 
- ~~**Timebox the “hacks”**~~  
  **Actually, no — I couldn’t.**  
  I initially planned to timebox any SDK deep-dives, but that flew out the window once I realized there was no moving forward without fixing the timeout issue. The problem was that the bug wasn’t obvious — **LiveKit’s documentation doesn’t mention anything about internal timeout handling, and there’s nothing in their "Getting Started" guide or official site that points to `APIConnectOptions` as the culprit**.  

  What made this worse: it wasn’t a bug in *my* code or even in the way I used the APIs — it was a mismatch between the timeout defaults in the LiveKit SDK and the strict limits of the free OpenAI and ElevenLabs tiers.  
  Once I finally found the `livekit/types.py` file and patched the internal timeout value, everything started working again — but that “simple” fix took hours to uncover.

## Final Thoughts
This project highlighted how subtle SDK defaults and undocumented behaviors can block progress — especially when working with strict API rate limits. It was a reminder that real-world debugging often means going beyond the docs and into the source. I’m proud of how I navigated those blockers and delivered a working real-time pipeline under pressure.