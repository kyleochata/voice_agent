from dotenv import load_dotenv

from livekit import agents
from livekit.agents import AgentSession, Agent, RoomInputOptions
from livekit.plugins import (
    openai,
    elevenlabs,
    deepgram,
    noise_cancellation,
    # silero,
)
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from intake_agent import Intake_Assistant

load_dotenv()



async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=openai.LLM(model="gpt-4o"),
        tts=elevenlabs.TTS(
            voice_id="ODq5zmih8GrVes37Dizd",
            model="eleven_multilingual_v2"
        ),
        turn_detection=MultilingualModel(),
    )

    assistant = Intake_Assistant()
    await session.start(
        room=ctx.room,
        agent=assistant,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await session.say("Hello! I'll be helping you with your information today. Let's start with your name.")
    await assistant.collect_information(session)


if __name__ == "__main__":
    agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))