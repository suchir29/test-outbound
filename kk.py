import asyncio
from livekit import api
from livekit.protocol.sip import CreateSIPOutboundTrunkRequest, SIPOutboundTrunkInfo

async def main():
    # Direct LiveKit credentials
    livekit_host = "wss://voice-ai-quickstart-rylsie7l.livekit.cloud"
    livekit_api_key = "APIQht9Da7ZYhVr"
    livekit_api_secret = "MLAdvN5Q6JLmfbV1i40M8TCnfNqV3VAPSIRI73fqRBbA"

    # Connect to LiveKit API using correct keyword 'url'
    lkapi = api.LiveKitAPI(
        url=livekit_host,
        api_key=livekit_api_key,
        api_secret=livekit_api_secret,
    )

    # Prepare SIP trunk info (DIDLogic)
    trunk = SIPOutboundTrunkInfo(
        name="didlogic-outbound",
        address="sip.nl.didlogic.net",
        numbers=["0031705680050"],
        auth_username="09372",
        auth_password="DQWqSfq8b594sxF"
    )

    request = CreateSIPOutboundTrunkRequest(trunk=trunk)

    try:
        result = await lkapi.sip.create_sip_outbound_trunk(request)
        print(f"✅ Successfully created SIP trunk: {result}")
    except Exception as e:
        print(f"❌ Failed to create SIP trunk: {e}")
    finally:
        await lkapi.aclose()

asyncio.run(main())
