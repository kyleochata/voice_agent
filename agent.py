import logging
from dotenv import load_dotenv
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Type
import dateutil.parser
from typing import Dict
import asyncio

from livekit.agents import JobContext, WorkerOptions, cli
from livekit.agents.llm import function_tool
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import deepgram, openai, elevenlabs, silero
from livekit import api
from utils.validate_insuance import validate_insurance_eligibility, check_insurance_eligibility

load_dotenv()
logger = logging.getLogger("declarative-flow")
logger.setLevel(logging.INFO)


@dataclass
class SurveyData:
    """Stores all survey responses and state"""
    responses: Dict[str, str] = field(default_factory=dict)
    current_stage: str = "stedi_send"
    path_taken: List[str] = field(default_factory=list)

    def record(self, question: str, answer: str):
        self.responses[question] = answer
        self.path_taken.append(f"Stage '{self.current_stage}' - {question}: {answer}")

class BaseAgent(Agent):
    """Base agent setup with transition logic"""
    def __init__(self, job_context: JobContext, instructions: str) -> None:
        self.job_context = job_context
        super().__init__(
            instructions=instructions,
            stt=deepgram.STT(),
            llm=openai.LLM(model="gpt-4o-mini", timeout=29.0),
            tts=elevenlabs.TTS(
                voice_id="ODq5zmih8GrVes37Dizd",
                model="eleven_multilingual_v2"),
            vad=silero.VAD.load()
        )
    async def transition(self) -> Optional[Agent]:
        current = self.session.state.get("current_node")
        next_fn = flow.get(current, {}).get("next")
        if not next_fn:
            return None
        next_node = next_fn(self.session.state)
        if next_node is None:
            return None
        self.session.state["current_node"] = next_node
        agent_cls: Type[Agent] = flow[next_node]["agent"]
        newAgent = agent_cls(self.job_context)
        print(newAgent)
        return newAgent

class DataCollectorAgent(BaseAgent):
    """Generic data collecting agent. Collect one piece of information and transition"""
    key: str
    label: str
    question: str
    instructions: str

    def __init__(self, job_context: JobContext) -> None:
        super().__init__(job_context=job_context, instructions=self.instructions)
    
    async def on_enter(self):
        await self.session.say(self.question)
    
    @function_tool
    async def collect(self, value: str) -> Optional[Agent]:
        sd: SurveyData = self.session.userdata
        sd.record(self.label, value)
        self.session.state[self.key] = value
        return await self.transition()
    
class Collect_FirstNameAgent(DataCollectorAgent):
    key = "first_name"
    label = "first_name"
    question = "What is your first name?"
    instructions = "Please tell me your first name."

class Collect_LastNameAgent(DataCollectorAgent):
    key = "last_name"
    label = "last_name"
    question = "What is your last name?"
    instructions = "Please tell me your last name."

class Collect_InsuranceAgent(DataCollectorAgent):
    key = "insurance_id"
    label = "insurance_id"
    question = "What is your insurance id or number?"
    instructions = "Please tell me your insurance id or number."

class Confirm_SpellbackAgent(BaseAgent):
    def __init__(self, job_context: JobContext) -> None:
        super().__init__(job_context=job_context, instructions="Confirm the information provided is correct by spelling it back")
    
    def spell_out(self, value: str, is_insurance_id: bool = False) -> str:
        """
        Convert a value into a spelled out version:
        - "John" -> "J O H N"
        - For insurance IDs, also handle numeric text conversion
        """
        if not value:
            return "empty"
            
        if is_insurance_id:
            number_mapping = {
                "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4",
                "five": "5", "six": "6", "seven": "7", "eight": "8", "nine": "9"
            }
            
            words = value.lower().split()
            result = []
            
            for word in words:
                if word in number_mapping:
                    # Convert number words to digits
                    result.append(number_mapping[word])
                else:
                    # Keep non-number words as is
                    result.append(word)    
            # Join back into a string with no spaces between numbers
            processed_value = "".join(result).upper()
            print(processed_value)
            return " ".join(processed_value)
        else:
            print(" ".join(value.upper()))
            return " ".join(value.upper())
    
    async def on_enter(self) -> None:
        # sd: SurveyData = self.session.userdata
        current_stage = self.session.state.get("current_node")
        
        # Determine what to spellback based on current stage
        if "fname_confirm" in current_stage:
            value = self.session.state.get("first_name")
            print(f"F_Name:\t {value}")
            spelled = self.spell_out(value)
            await self.session.say(f"I heard your first name as {value}, spelled {spelled}. Is that correct?")
        elif "lname_confirm" in current_stage:
            value = self.session.state.get("last_name")
            print(f"L_Name:\t {value}")
            spelled = self.spell_out(value)
            await self.session.say(f"I heard your last name as {value}, spelled {spelled}. Is that correct?")
        elif "dob_confirm" in current_stage:
            # Use the raw date string that was stored
            value = self.session.state.get("dob_raw", "")
            print(f"DOB Raw: {value}")
            await self.session.say(f"I heard your date of birth as {value}. Is that correct?")
        elif "insurance_confirm" in current_stage:
            value = self.session.state.get("insurance_id")
            spelled = self.spell_out(value, is_insurance_id=True)
            
            # For insurance ID, also tell the user what it was converted to
            processed_value = "".join([char for char in spelled if char != " "])
            self.session.state["insurance_id"] = processed_value
            await self.session.say(f"I heard your insurance ID as {self.session.state["insurance_id"]}, spelled {spelled}. Is that correct?")
    
    @function_tool
    async def confirm(self, is_correct: bool) -> Optional[Agent]:
        self.session.state["confirm"] = is_correct

        return await self.transition()

class Collect_DOBAgent(DataCollectorAgent):
    key = "date_of_birth"
    label = "date_of_birth"
    question = "What is your date of birth? Please provide it in the format of month, day, year."
    instructions = "Collect the user's date of birth in a format that can be converted to YYYYMMDD for the Stedi API."

    @function_tool
    async def collect(self, value: str) -> Optional[Agent]:
        sd: SurveyData = self.session.userdata
        sd.record(self.label, value)

        self.session.state["string_date"] = value
        parsed_date = dateutil.parser.parse(value)
        formatted_date = parsed_date.strftime("%Y%m%d")
        self.session.state[self.key] = formatted_date
        print(f"parsedDate: {self.session.state.get(self.key)}")
        self.session.state["dob_raw"] = value
        print(f"rawDateStr: {self.session.state.get("dob_raw")}")
        
        return await self.transition()


class Stedi_CheckAgent(BaseAgent):
    def __init__(self, job_context: JobContext) -> None:
        super().__init__(job_context=job_context, instructions="Check insurance information with Stedi API and inform user of the result")
    
    async def on_enter(self) -> None:
        await self.session.say("Thank you. I am now checking your insurance information. Please hold.")
        
        first_name = self.session.state.get("first_name", "").lower().capitalize() or "Jane"
        last_name = self.session.state.get("last_name",  "").lower().capitalize() or "Doe"
        insurance_id = self.session.state.get("insurance_id", "AETNA12345")
        insurance_id = "".join(insurance_id.split()) or "AETNA12345"
        date_of_birth = self.session.state.get("date_of_birth", "20040404") 
        
        # Get current retry count from session state
        retry_count = self.session.state.get("insurance_validation_retry_count", 0)
        
        # Call the external API function
        api_result = await check_insurance_eligibility(
            first_name=first_name,
            last_name=last_name,
            insurance_id=insurance_id,
            date_of_birth=date_of_birth,
            retry_count=retry_count
        )
        
        if not api_result["success"]:
            # Handle API error
            if retry_count < 1:
                await self.session.say("I'm sorry, but we encountered a technical problem verifying your insurance.")
                self.session.state["needs_representative"] = True
                print(f" need rep: \t{self.session.state.get('needs_representative')}")  # Fixed quotes
            else:
                await self.session.say("I'm having trouble verifying your insurance information. Let's try again.")
                self.session.state["insurance_verified"] = False
                self.session.state["retry_validation"] = True
                self.session.state["insurance_validation_retry_count"] = retry_count + 1
        else:
            # Only process the response if the API call was successful
            response_data = api_result["data"]
            validation_result = validate_insurance_eligibility(response_data, retry_count)
            
            # Store validation results in session state
            self.session.state["insurance_verified"] = validation_result["is_valid"]
            self.session.state["insurance_active"] = validation_result["active_insurance"]
            self.session.state["has_office_coverage"] = validation_result["has_office_visit_coverage"]
            self.session.state["network_status"] = validation_result["network_status"]
            self.session.state["copay_amount"] = validation_result["copay_amount"]
            
            # Set flags for flow control
            self.session.state["needs_representative"] = validation_result["needs_representative"]
            self.session.state["retry_validation"] = validation_result["retry_validation"]
            
            # If we need to retry, increment the counter
            if validation_result["retry_validation"]:
                self.session.state["insurance_validation_retry_count"] = retry_count + 1
            
            # Communicate results to the user
            await self.session.say(validation_result["message"])
        
        print(f"About to transition with needs_representative={self.session.state.get('needs_representative')}")
        return await self.transition()



# Fix for TransferToRepresentativeAgent
class TransferToRepresentativeAgent(BaseAgent):
    def __init__(self, job_context: JobContext) -> None:
        super().__init__(job_context=job_context, instructions="Transfer the user to a representative")
    
    async def on_enter(self) -> None:
        await self.session.say("Connecting to a human representative to help. Please stay on the line.")
        await self.session.aclose()
        try: 
            await self.job_context.api.room.delete_room(
                api.DeleteRoomRequest(room=self.job_context.room.name)
            )
        except Exception as e:
            logger.error(f"Error deleting room: {e}")


    

class EndingAgent(BaseAgent):
    def __init__(self, job_context: JobContext) -> None:
        super().__init__(job_context=job_context, instructions="Conclude the conversation with a friendly goodbye")
    
    async def on_enter(self) -> None:
        await self.session.say("Thank you for verifying your insurance. Goodbye")
        await self.session.aclose()
        try: 
            await self.job_context.api.room.delete_room(
                api.DeleteRoomRequest(room=self.job_context.room.name)
            )
        except Exception as e:
            logger.error(f"Error deleting room: {e}")

flow = {
    "collect_fname": {
        "agent": Collect_FirstNameAgent,
        "next": lambda state: "fname_confirm"
    },
    "fname_confirm": {
        "agent": Confirm_SpellbackAgent,
        "next": lambda state: "collect_lname" if state.get("confirm", True) else "collect_fname"
    },
    "collect_lname": {
        "agent": Collect_LastNameAgent,
        "next": lambda state: "lname_confirm"
    },
    "lname_confirm": {
        "agent": Confirm_SpellbackAgent,
        "next": lambda state: "collect_dob" if state.get("confirm", True) else "collect_lname"
    },
    "collect_dob": {
        "agent": Collect_DOBAgent,
        "next": lambda state: "dob_confirm"
    },
    "dob_confirm": {
        "agent": Confirm_SpellbackAgent,
        "next": lambda state: "collect_insurance" if state.get("confirm", True) else "collect_dob"
    },
    "collect_insurance": {
        "agent": Collect_InsuranceAgent,
        "next": lambda state: "insurance_confirm"
    },
    "insurance_confirm": {
        "agent": Confirm_SpellbackAgent,
        "next": lambda state: "stedi_send" if state.get("confirm", True) else "collect_insurance"
    },
    "stedi_send": {
        "agent": Stedi_CheckAgent,
        "next": lambda state: "transfer_to_rep" if state.get("needs_representative", False) 
                else "collect_insurance" if state.get("retry_validation", False)
                else "goodbye"
    },
    "transfer_to_rep": {
        "agent": TransferToRepresentativeAgent,
        "next": None
    },
    "goodbye": {
        "agent": EndingAgent,
        "next": None
    }
}




async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    session = AgentSession()
    session.userdata = SurveyData()
    session.state = {"current_node": "collect_fname"}
    await session.start(agent=Collect_FirstNameAgent(ctx), room=ctx.room)

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))