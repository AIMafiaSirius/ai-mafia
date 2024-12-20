from ai_mafia.llm import main


class Npc:
    def __init__(self, role):
        #self.adress = adress
        #self.key = key
        self.role = role

    def greeting(self, game_story):
        q = f'the story of game was: {game_story}, you are 3rd player, answer them a short greeting. Tell me only your answer'
        main(q)

    def vote(self, game_story):
        if self.role == 0:
            q = f'the story game was: {game_story}. You are mafia! Don`t be suspicious, you goal is win of mafias, choose person, you want to vote for. Tell me only number of player ypu want to vote!'
            main(q)
        else:
            q = f'the story game was: {game_story}. You should understand who is mafia and vote him. Tell me only number!'
            main(q)
    def speak(self, game_story):
        q = f'the story was: {game_story}. Prove that you are not mafia! don`t be suspicious!. Tell me only your speech!'
        main(q)


data = 'player1 told: "hi, how are you?", player2 told: "I`m fine and wonder if other are okay?"'
player = Npc(1)
player.greeting(data)
data = 'player1 told: "I`m mafia", player2 told:"bla-bla-bla", player3 told: "boo"'
player.vote(data)
data = 'player1: I told all!, player2: I think player 2 is mafia, player3: I think player 1 is mafia, player4: I don`t know nothing'
player.speak(data)