import chatsky.conditions as cnd
import chatsky.destinations as dst
from chatsky import RESPONSE, TRANSITIONS, Pipeline, PRE_RESPONSE
from chatsky import Transition as Tr
import random


players = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

players_id = []
# массив used нужны id телеграммов игроков

mafia_id = []
# id телегоаммов мафии

mafia = []
# номера мафии

cards = {0: "Мирный",
         1: "Комиссар",
         2: "Мафия",
         3: "Дон мафии"}
# карты в int

players_role = [2, 2, 3, 1, 0, 0, 0, 0, 0, 0]
# роли игкоков


def mixed_role():
    for i in range(len(players_role)):
        r = random.randint(0, i)
        players_role[i], players_role[r] = players_role[r], players_role[i]
    return players_role


def get_role_for_all():
    role = ""
    for i in range(10):
        if i != 9:
            role = role + "Ваша роль: " + cards[players_role[i]] + "\n"
        else:
            role = role + "Ваша роль: " + cards[players_role[i]]

    return role



number_of_living_players = len(players)

players_role = mixed_role()

mafia_get_role = {
    "greeting_flow": {
        "start_node": {
            TRANSITIONS: [Tr(dst="greeting_node", cnd=cnd.ExactMatch("/start"))]

        },
        "greeting_node": {
            RESPONSE: "Начало игры, раздача карт!",
            TRANSITIONS: [Tr(dst=("mafia_get_role_flow", "get_role1"))],
        },
        "fallback_node": {
            RESPONSE: "That was against the rules",
            TRANSITIONS: [Tr(dst="greeting_node")],
            # не правильный текст
        },
    },
    "mafia_get_role_flow": {
        "get_role1": {
            RESPONSE: get_role_for_all(),
        },
    },
}

pipeline = Pipeline(
    mafia_get_role,
    start_label=("greeting_flow", "start_node"),
    fallback_label=("greeting_flow", "fallback_node"),
)

if __name__ == "__main__":
    pipeline.run()
