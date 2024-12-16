import chatsky.conditions as cnd
import chatsky.destinations as dst
from chatsky import RESPONSE, TRANSITIONS, Pipeline, BaseCondition, Context
from chatsky import Transition as Tr

self_num = 3

checking_players = {1:1, 2:0, 3:3, 4:2, 5:2, 6:0, 7:0, 8:1, 9:0, 10:0}
players = checking_players
request = None
def check_votes():
    max_res = 0
    num_of_max = 0
    for player in players:
        if players[player] > max_res:
            max_res = players[player]
            num_of_max = 1
        elif players[player] == max_res:
            max_res += 1
    print(num_of_max)
    if num_of_max > 1:
        print("was the same")
        return False
    else:
        print("will exclude")
    return True

def get_person_to_exclude():
    max_res = 0
    ex = []
    for player in players:
        if players[player] > max_res:
            max_res = players[player]
            ex = [player]
        elif players[player] == max_res:
            ex.append(player)
    return ex

class get_vote(BaseCondition):
    global request
    async def call(self, ctx: Context) -> bool:
        request = ctx.last_request
        print(f"you voted {request}")
        return True

voting_script = {
    "voting_flow":{
        "start_node":{
            TRANSITIONS: [Tr(dst="vote_node", cnd=cnd.ExactMatch("/start"))]
        },

        "fallback_node": {
            RESPONSE: "You`ve done something wrong",
            TRANSITIONS: [Tr(dst="greeting_node")],
        },


        "vote_node":{
            RESPONSE: "Choose person who you want to exclude",
            TRANSITIONS: [ Tr(dst='voted_node', cnd=get_vote())]
        },
        
        "voted_node":{
            RESPONSE: f"you choose player {request}, right?",
            TRANSITIONS: [Tr(dst="exclude_node", cnd = check_votes()), Tr(dst='second_vote_node', cnd = not check_votes)]
        },
        "second_vote_node":{
            RESPONSE: "chosen players have a minute to their speech",
            TRANSITIONS: [Tr(dst="end_node")]
        },
        "exclude_node":{
            RESPONSE: f"{get_person_to_exclude()} was excluded" if get_person_to_exclude!= self_num else "You`ve been excluded",
            TRANSITIONS: [Tr(dst="end_node")]
        },
        "end_node":{
            RESPONSE: "This is the end",
            TRANSITIONS: [Tr(dst="start_node")]
        }

    }
}
pipeline = Pipeline(
    voting_script,
    start_label=("voting_flow", "start_node"),
    fallback_label=("voting_flow", "fallback_node"),
)

if __name__ == "__main__":
    pipeline.run()

