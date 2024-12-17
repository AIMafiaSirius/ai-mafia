import chatsky.conditions as cnd
import chatsky.destinations as dst
from chatsky import GLOBAL, RESPONSE, TRANSITIONS, Pipeline
from chatsky import Transition as Tr

ping_pong_script = {
    "greeting_flow": {
        "start_node": {
            TRANSITIONS: [Tr(dst="greeting_node", cnd=cnd.ExactMatch("/start"))]
            # start node handles the initial handshake (command /start)
        },
        "greeting_node": {
            RESPONSE: "Hi!",
            TRANSITIONS: [Tr(dst=("ping_pong_flow", "game_start_node"), cnd=cnd.ExactMatch("Hello!"))],
        },
        "fallback_node": {
            RESPONSE: "That was against the rules",
            TRANSITIONS: [Tr(dst="greeting_node")],
            # this transition is unconditional
        },
    },
    "ping_pong_flow": {
        "game_start_node": {
            RESPONSE: "Let's play ping-pong!",
            TRANSITIONS: [Tr(dst="response_node", cnd=cnd.ExactMatch("Ping!"))],
        },
        "response_node": {
            RESPONSE: "Pong!",
            TRANSITIONS: [Tr(dst=dst.Current(), cnd=cnd.ExactMatch("Ping!"))],
        },
    },
}

pipeline = Pipeline(
    ping_pong_script,
    start_label=("greeting_flow", "start_node"),
    fallback_label=("greeting_flow", "fallback_node"),
)

if __name__ == "__main__":
    pipeline.run()
