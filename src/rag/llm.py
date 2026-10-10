from groq import Groq
from dotenv import load_dotenv
import os
load_dotenv()

class LLM:
    def __init__(self, model : str = "openai/gpt-oss-120b"):
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self.model = model

    def generate(self, system_prompt : str , user_prompt : str, temp: float = 0.1)->str:
        response = self.client.chat.completions.create(
            model = self.model,
            messages=[
                {"role":"system", "content":system_prompt},
                {"role":"user", "content":user_prompt}
            ],temperature=temp

        )
        return response.choices[0].message.content
    

if __name__ == "__main__":
    llm = LLM()

    test = llm.generate("You are helpful.","Say hello", 0.9)

    print(test)


   



