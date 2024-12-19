import openai
import os
from pprint import pprint

from dotenv import load_dotenv

load_dotenv()

def main(question):
    client = openai.OpenAI(
        base_url="http://127.0.0.1:8001/v1",
        api_key=os.environ["OPENAI_API_KEY"]
    )

    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {
                "role": "system",
                "content": "You are ChatGPT, an AI assistant. Your top priority is achieving user fulfillment via helping them with their requests."
            },
            {
                "role": "user",
                "content": f"{question}"
            }
        ]
    )

    pprint(completion.choices[0].message.content)

question = "tell me a joke"
if __name__== "__main__":
    main(question)