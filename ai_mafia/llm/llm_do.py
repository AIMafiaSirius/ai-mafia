import os

import openai
from dotenv import load_dotenv

load_dotenv()


def get_response(question):
    client = openai.OpenAI(base_url="http://127.0.0.1:8001/v1", api_key=os.environ["OPENAI_API_KEY"])

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are player in game 'Mafia'."},
            {"role": "user", "content": f"{question}"},
        ],
    )

    return completion.choices[0].message.content


question = "tell me a joke"
if __name__ == "__main__":
    get_response(question)
