from groq import Groq

from src.config import settings
from src.metrics import LLM_CALL_SECONDS, LLM_FAILURES


class LLM:
    def __init__(self, model: str = settings.model_name):
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = model

    def generate(self, system_prompt: str, user_prompt: str, temp: float = 0.1) -> str:
        with LLM_CALL_SECONDS.time():  # times the call, success or failure
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temp,
                )
            except Exception:
                LLM_FAILURES.inc()  # count it...
                raise  # ...then let the caller handle it as before
        return response.choices[0].message.content


if __name__ == "__main__":
    llm = LLM()
    print(llm.generate("You are helpful.", "Say hello", 0.9))