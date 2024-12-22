from fastapi import FastAPI
from pydantic import BaseModel
from ai_mafia.llm import get_response

app = FastAPI()

class Npc:
    def __init__(self, role):
        self.role = role

    def greeting(self, game_story):
        q = f"the story of game was: {game_story}, you are 3rd player, answer them a short greeting. Tell me only your answer"
        response = get_response(q)
        return response

    def vote(self, game_story):
        if self.role == 0:
            q = f"The story game was: {game_story}. You are mafia! Dont be suspicious, you goal is win of mafias, choose person, you want to vote for. Tell me only number!!"
            response = get_response(q)
            return response
        else:
            q = f"The story of game was: {game_story} choose person, you want to vote for. Tell me only number!!!"
            response = get_response(q)
            return response

    def speak(self, game_story):
        q = f"the story was: {game_story}. You are player. Prove that you are not mafia! dont be suspicious!. Tell me only your short speech!"
        response = get_response(q)
        return response

class NpcRequest(BaseModel):
    role: int
    game_story: str

npc_instance = None

@app.post("/npc/greeting")
async def npc_greeting(request: NpcRequest):
    npc_instance = Npc(request.role)
    response = npc_instance.greeting(request.game_story)
    return {"response": response}

@app.post("/npc/vote")
async def npc_vote(request: NpcRequest):
    npc_instance = Npc(request.role)
    response = npc_instance.vote(request.game_story)
    return {"response": response}

@app.post("/npc/speak")
async def npc_speak(request: NpcRequest):
    npc_instance = Npc(request.role)
    response = npc_instance.speak(request.game_story)
    return {"response": response}


