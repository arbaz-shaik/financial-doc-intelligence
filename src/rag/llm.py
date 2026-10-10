from groq import Groq
from src.config import settings

class LLM:
    def __init__(self, model : str = settings.model_name):
        self.client = Groq(api_key= settings.groq_api_key)
        self.model =  model

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


   



