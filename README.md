# LiveKit Coding Challenge Submission

## Overview
I was able to complete the most of the requirement of the challenge. Created an Ai voice agent that intakes the users fist, last names, date of birth and insurance id. It then calls on the STEDI api and parses through the data coming back and makes decisions based on returned data.  

## Completed Work
- [x] Implemented the basic WebSocket connection to LiveKit
- [x] Established initial room participation logic
- [x] Intake of first name, with confirmation. (spelled back to user with phonetic alphabet)
- [x] Intake of last name, with confirmation. (spelled back to user with phonetic alphabet)
- [x] Intake of insurance ID. 
- [x] Intake of DOB (date of birth)
- [x] API post to STEDI
- [x] Insurance validation
- [x] Closing?
    - Kind of...did a hardcoded a hacky work around. See known issues for more information

- Demo of completed Work:
    - https://drive.google.com/file/d/1bTQ5jsyInGLzvSnq04Jz2s6kL3carpwv/view?usp=sharing

## Challenges Faced
1. **LiveKit Learning Curve**: Understanding the LiveKit ecosystem and WebSocket protocol took significant time. 

2. **API Usage Constraints**: I ran into multiple usage limits for the OpenAPI and Elevenlabs APIs
    - Literally was on my last email using up the last of the monthly credits for elevenlabs.
    - Had to slow the program down as seen in the demo with timeouts and slow server retries. 
3. **ElevenLabs API Usage Constraints**: Just had to mention this twice.
4. **Python**: I have maybe one other project with python in the last 6 months so it was a dash to get back to speed.
    - I was prepping TypeScript and Node in the days leading up to this and was rather shocked by livekits documentation and the challenge being in Python.
    - The reason I chose Python over the experimental Typescript was due to there being more documentation with the python files. 
    - It was enjoyable to be put to the fire and see how much I was able to get done while not prepping the language.

## Next Steps (If Given More Time)


1. Create tests to dradtically reduce API calls. 

2. Figure out why the flow architecture taken from https://github.com/livekit-examples/python-agents-examples/blob/main/flows/declarative_flow.py breaks after the `stedi_send`
    - Unsure and couldn't find much information on why the declarative flow breaks.
3. As a extension of 2, there is a decision tree where the unsuccessful first insuance call may or maynot redirect the node stat back to the `"insurance_collection"` state. 
    - This is working 50% of the time. 
    - I do think this is due to the overall structure of the Stedi_CheckAgent.
    - SOLUTION:
        - Change it to a deciscion based flow: https://github.com/livekit-examples/python-agents-examples/blob/main/flows/multi_stage_flow.py
        - Potential issues: 
            - Need to see how switching workflows mid progam works. May need addition helpers to get it from one workflow architecture to another. More research needed. 
4. Modularize the code.
    - Tried to do it at the end but ran into circular dependency issues. Depending on when this is viewed, I may have fixed this.

## Key Learnings
Through this challenge, I've gained:
- Basic understanding of LiveKit's WebSocket API
- Experience working with real-time communication protocols
- Python nuancess 

## Known Issues 
- Due to api usage rates of my free tier, I modified the livekit.types file to increase the timeout and connections to openai and elevenlabs.
    - Both are very tempermental and elevenlabs doesn't like when the pause is > 30s. Throws a 500 error.
- The final workflow to after the insurance checks are stopping. The agents are getting created but their `session.say()` aren't working. Even manually calling it out of the `Stedi_check_agent` didn't solve anything.
    - This is where I would lean on other team members for more help due to not being able to find anything related online and shoving the data into a LLM didn't seem to help either.

- During date of birth readback the ai agent is only picking up the handled and parsed date rather than reading back what the user says to it.
    - Must be something overwriting a dict key value pairing or I am doing things out of order


# Usage
Please ensure that there is a .env file at the root directory that mimics the `.env.example`:
```
- DEEPGRAM_API_KEY=
- OPENAI_API_KEY=
- ELEVEN_API_KEY=
- LIVEKIT_URL=
- LIVEKIT_API_KEY=
- LIVEKIT_API_SECRET=
- STEDI_API_KEY=
```

In the console please run `python agent.py download-files`, followed by `python agent.py console` to interact with the voice-agent. 

If you just want to check the STEDI api call, There are some hardcoded default values as to not waste any elevnlabs credits.
1. Navigate to agent.py
2. Replace the async def entrypoint in agent.py to the following:

```
    async def entrypoint(ctx: JobContext) -> None:
        await ctx.connect()
        session = AgentSession()
        session.userdata = SurveyData()
        session.state = {"current_node": "stedi_send"}
        await session.start(agent=Stedi_CheckAgent(ctx), room=ctx.room)

    if __name__ == "__main__":
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
```

3. The defaulted information is for following STEDI POST call:
```
    curl --request POST \
  --url 'https://healthcare.us.stedi.com/2024-04-01/change/medicalnetwork/eligibility/v3' \
  --header 'Authorization: Key {test_api_key}' \
  --header 'Content-Type: application/json' \
  --data '{
    "controlNumber":"112233445",
    "tradingPartnerServiceId": "60054",
    "provider": {
        "organizationName": "Provider Name",
        "npi": "1999999984"
    },
    "subscriber": {
        "firstName": "Jane",
        "lastName": "Doe",
        "dateOfBirth": "20040404",
        "memberId": "AETNA12345"
    },
    "encounter": {
        "serviceTypeCodes": ["30"]
    }
}'
```

4. To change the default to check other STEDI POST calls without running through the whole program (save your credits), navigate to `agent.py` and find the class shown below:

```
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
```

Feel free to change the default information to test as needed. 

# Acknowledgements

I would like to thank Pablo and Tannen for the enjoyable challenge and helping expand my horizons with my skills in programming. All the best!

## Contact Me

linkedIn: https://linkedin.com/in/kyle-etrata






