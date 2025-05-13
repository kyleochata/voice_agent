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
from typing import Optional, Dict, Tuple

load_dotenv()


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""
            You are an information collection assistant. Your ONLY task is to:
            1. Ask for the user's first name and confirm it by spelling it back to them
            2. Ask for the user's last name and confirm it by spelling it back
            3. Ask for the user's insurance ID and confirma it by spelling it back
            4. Verify all information is correct
""" 
        ) 
        self.user_data: Dict[str, Optional[str]] = {
            "first_name": None,
            "last_name": None,
            "insurance_id": None
        }
        self.data_collected = False
        self.confirmed = False

    async def spell_out(self, text: str) -> str:
        """Convert text to NATO phonetic alphabet spelling"""
        phonetic_alphabet = {
            'a': 'Alpha', 'b': 'Bravo', 'c': 'Charlie', 'd': 'Delta',
            'e': 'Echo', 'f': 'Foxtrot', 'g': 'Golf', 'h': 'Hotel',
            'i': 'India', 'j': 'Juliet', 'k': 'Kilo', 'l': 'Lima',
            'm': 'Mike', 'n': 'November', 'o': 'Oscar', 'p': 'Papa',
            'q': 'Quebec', 'r': 'Romeo', 's': 'Sierra', 't': 'Tango',
            'u': 'Uniform', 'v': 'Victor', 'w': 'Whiskey', 'x': 'X-ray',
            'y': 'Yankee', 'z': 'Zulu',
            '0': 'Zero', '1': 'One', '2': 'Two', '3': 'Three',
            '4': 'Four', '5': 'Five', '6': 'Six', '7': 'Seven',
            '8': 'Eight', '9': 'Nine'
        }
        
        spelled_out = []
        for char in text.lower():
            if char in phonetic_alphabet:
                spelled_out.append(phonetic_alphabet[char])
            elif char == ' ':
                spelled_out.append('Space')
            else:
                spelled_out.append(char.upper())
        return ' '.join(spelled_out)

    async def collect_name_part(self, session: AgentSession, name_type: str) -> Tuple[bool, str]:
        """Helper function to collect and confirm a name part (first or last)"""
        await session.say(f"May I have your {name_type.replace('_', ' ')} please?")
        name = await session.listen_for_text()
        
        spelled_name = await self.spell_out(name)
        await session.say(f"I have your {name_type.replace('_', ' ')} as {name}. That's {spelled_name}. Is that correct?")
        
        confirmation = await session.listen_for_text()
        return "no" not in confirmation.lower(), name

    async def collect_insurance_id(self, session: AgentSession) -> Tuple[bool, str]:
        """Helper function to collect and confirm insurance ID"""
        await session.say("Now, may I have your insurance ID number?")
        insurance_id = await session.listen_for_text()
        
        spelled_id = await self.spell_out(insurance_id)
        await session.say(f"I have your insurance ID as {insurance_id}. That's {spelled_id}. Is that correct?")
        
        confirmation = await session.listen_for_text()
        return "no" not in confirmation.lower(), insurance_id

    async def collect_information(self, session: AgentSession):
        # Collect first name
        if not self.user_data["first_name"]:
            success, first_name = await self.collect_name_part(session, "first name")
            if not success:
                return await self.collect_information(session)
            self.user_data["first_name"] = first_name

        # Collect last name
        if not self.user_data["last_name"]:
            success, last_name = await self.collect_name_part(session, "last name")
            if not success:
                # Clear first name if last name is wrong to start fresh
                self.user_data["first_name"] = None
                return await self.collect_information(session)
            self.user_data["last_name"] = last_name

        # Collect insurance ID
        if not self.user_data["insurance_id"]:
            success, insurance_id = await self.collect_insurance_id(session)
            if not success:
                # Don't clear names if just insurance ID is wrong
                self.user_data["insurance_id"] = None
                return await self.collect_information(session)
            self.user_data["insurance_id"] = insurance_id

        # Final confirmation
        if not self.confirmed:
            full_name = f"{self.user_data['first_name']} {self.user_data['last_name']}"
            spelled_name = await self.spell_out(full_name)
            spelled_id = await self.spell_out(self.user_data["insurance_id"])
            
            await session.say(f"Let me confirm all information. Your name is {full_name}. That's {spelled_name}. Your insurance ID is {self.user_data['insurance_id']}. That's {spelled_id}. Is everything correct?")
            
            final_confirmation = await session.listen_for_text()
            if "no" in final_confirmation.lower():
                self.user_data = {"first_name": None, "last_name": None, "insurance_id": None}
                return await self.collect_information(session)
            
            self.confirmed = True
            await session.say("Thank you for confirming. Your information has been received and will be processed.")
            print("Data ready for API call:", self.user_data)

#TODO: fetch the user_data information in STEDI wanted format. 
    async def STEDI_fetch(self, session: AgentSession): 
        pass

#TODO: parse the fetch information into relevant areas: insurance_active: bool, STC_98: bool, provider_in_network: bool; copay: int or string?
    async def STEDI_parse(self, session: AgentSession):
        #self.STEDI_fetch()
        pass
#TODO: pass off Stedi_parse informatioin to a following agent:
    async def handoff_to_next_agent(self, session: AgentSession):
        #newAgent = new Agent(...)
        pass

async def entrypoint(ctx: agents.JobContext):
    await ctx.connect()

    session = AgentSession(
        stt=deepgram.STT(model="nova-3", language="multi"),
        llm=openai.LLM(model="gpt-4o-mini"),
        tts=elevenlabs.TTS(
            voice_id="ODq5zmih8GrVes37Dizd",
            model="eleven_multilingual_v2"
        ),
        turn_detection=MultilingualModel(),
    )

    assistant = Assistant()
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