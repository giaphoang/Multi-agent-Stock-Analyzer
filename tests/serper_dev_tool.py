from crewai_tools import SerperDevTool
from dotenv import load_dotenv
from pathlib import Path

env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path, override=False)

tool = SerperDevTool(
    country="fr",
    locale="fr",
    location="Paris, Paris, Ile-de-France, France",
    n_results=2,
)

print(tool.run(search_query="Jeux Olympiques"))
