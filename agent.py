from __future__ import annotations

import asyncio
import logging
import os
import json
from typing import Any
from dotenv import load_dotenv
from openai.types.beta.realtime.session import TurnDetection


from livekit import rtc, api
from livekit.agents import (
    AgentSession,
    Agent,
    JobContext,
    function_tool,
    RunContext,
    get_job_context,
    cli,
    WorkerOptions,
    RoomInputOptions,
)
from livekit.plugins import (
    noise_cancellation,
    openai,
)

# Load env
load_dotenv(dotenv_path=".env.local")

logger = logging.getLogger("outbound-caller")
logger.setLevel(logging.INFO)

outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID")


class OutboundCaller(Agent):
    def __init__(
        self,
        *,
        instructions: str,
        dial_info: dict[str, Any],
    ):
        super().__init__(instructions=instructions)
        self.participant: rtc.RemoteParticipant | None = None
        self.dial_info = dial_info

    def set_participant(self, participant: rtc.RemoteParticipant):
        self.participant = participant

    async def hangup(self):
        job_ctx = get_job_context()
        await job_ctx.api.room.delete_room(
            api.DeleteRoomRequest(room=job_ctx.room.name)
        )

    @function_tool()
    async def transfer_call(self, ctx: RunContext):
        transfer_to = self.dial_info.get("transfer_to")
        if not transfer_to:
            return "Cannot transfer call. No transfer number provided."

        logger.info(f"Transferring call to {transfer_to}")
        await ctx.session.generate_reply(instructions="I’ll transfer you now.")

        job_ctx = get_job_context()
        try:
            await job_ctx.api.sip.transfer_sip_participant(
                api.TransferSIPParticipantRequest(
                    room_name=job_ctx.room.name,
                    participant_identity=self.participant.identity,
                    transfer_to=f"tel:{transfer_to}",
                )
            )
        except Exception as e:
            logger.error(f"Error transferring call: {e}")
            await ctx.session.generate_reply(
                instructions="There was an error transferring the call."
            )
            await self.hangup()

    @function_tool()
    async def end_call(self, ctx: RunContext):
        logger.info(f"Ending call for {self.participant.identity}")
        if ctx.session.current_speech:
            await ctx.session.current_speech.wait_for_playout()
        await self.hangup()

    @function_tool()
    async def look_up_availability(self, ctx: RunContext, date: str):
        logger.info(f"Checking availability for {self.participant.identity} on {date}")
        await asyncio.sleep(3)
        return {"available_times": ["1pm", "2pm", "3pm"]}

    @function_tool()
    async def confirm_appointment(self, ctx: RunContext, date: str, time: str):
        logger.info(f"Confirming appointment for {self.participant.identity} on {date} at {time}")
        return "Appointment confirmed"

    @function_tool()
    async def detected_answering_machine(self, ctx: RunContext):
        logger.info(f"Voicemail detected for {self.participant.identity}")
        await self.hangup()


async def entrypoint(ctx: JobContext):
    logger.info(f"Connecting to room {ctx.room.name}")
    await ctx.connect()

    # Parse metadata
    dial_info = json.loads(ctx.job.metadata)
    participant_identity = phone_number = dial_info["phone_number"]

    # Load prompt
    prompt_path = os.path.join(os.path.dirname(__file__), "promptPaul.txt")
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            prompt_text = f.read()
    else:
        prompt_text = (
            "You are a polite voice assistant helping with appointment scheduling. "
            "Confirm details, offer alternative times, and allow transfer to a human if asked."
        )

    agent = OutboundCaller(
        instructions=prompt_text,
        dial_info=dial_info,
    )

    session = AgentSession(
        llm=openai.realtime.RealtimeModel(
            model="gpt-4o-mini-realtime-preview",
            voice="shimmer",
            temperature=1.0,
            turn_detection=TurnDetection(
                type="semantic_vad",
                eagerness="high",
                create_response=True,
                interrupt_response=True,
            ),
        ),
    )

    session_started = asyncio.create_task(
        session.start(
            agent=agent,
            room=ctx.room,
            room_input_options=RoomInputOptions(
                noise_cancellation=noise_cancellation.BVCTelephony(),
            ),
        )
    )

    try:
        await ctx.api.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=ctx.room.name,
                sip_trunk_id=outbound_trunk_id,
                sip_call_to=phone_number,
                participant_identity=participant_identity,
                wait_until_answered=True,
            )
        )

        await session.start(
                    agent=agent,
                    room=ctx.room,
                    room_input_options=RoomInputOptions(
                        noise_cancellation=noise_cancellation.BVCTelephony(),
                    ),
                )

        participant = await ctx.wait_for_participant(identity=participant_identity)
        agent.set_participant(participant)
        #await asyncio.sleep(1) 
        #await session.speak(text="Good day, am I speaking with Mr Ranbeer?")

        
    except api.TwirpError as e:
        logger.error(
            f"Error creating SIP participant: {e.message}, "
            f"SIP status: {e.metadata.get('sip_status_code')} {e.metadata.get('sip_status')}"
        )
        ctx.shutdown()


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            agent_name="outbound-caller",
        )
    )
