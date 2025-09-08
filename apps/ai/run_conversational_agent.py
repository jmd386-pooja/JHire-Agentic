import asyncio
from dotenv import load_dotenv

load_dotenv()


async def main():
    from governing_agent import GoverningAgent

    print("\nConversational Recruiting Agent (Governing Router)")
    print("===================================================")
    print("Ask anything. Examples:")
    print("  • how many data science developers do we have")
    print("  • list emails of Django folks in Bangalore")
    print("  • rank top 5: Junior Python developer, remote, degree not required")
    print("  • send congratulations to top 3 with username password and exam link")
    print("  • send rejection to Jane Doe, John Smith")
    print("Type 'quit' to exit.")

    agent = GoverningAgent()

    while True:
        try:
            user = input("\nYou: ").strip()
            if not user:
                continue
            if user.lower() in ("quit", "exit"):
                break
            reply = await agent.handle(user)
            print(f"Agent: {reply}")
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    asyncio.run(main())
