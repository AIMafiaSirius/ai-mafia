import random

import chatsky.conditions as cnd
from chatsky import PRE_RESPONSE, RESPONSE, TRANSITIONS, BaseResponse, Context, MessageInitTypes, Pipeline, dst
from chatsky import Transition as Tr
from chatsky.processing import ModifyResponse

jokes = [
    "Why don't scientists trust atoms? Because they make up everything!",
    "What do you call fake spaghetti? An impasta.",
    "How does the moon cut his hair? Eclipse it.",
    "What do you call a can opener that doesn't work? A can't opener.",
    "How many tickles does it take to make an octopus laugh? Ten-tickles.",
    "What do you get when you cross a snowman and a vampire? Frostbite.",
    "Why was the math book sad? Because it had too many problems.",
    "What do you call a sleeping bull? A bulldozer.",
    "Why can't you give Elsa a balloon? Because she will let it go.",
    "Knock, knock. Who's there? Lettuce. Lettuce who? Lettuce in, it's too cold out here!",
]


class RandomJoke(ModifyResponse):
    async def modified_response(self, _: BaseResponse, __: Context) -> MessageInitTypes:
        return random.choice(jokes) + "\n\nDid you laugh?"


ping_pong_script = {
    "flow": {
        "start_node": {TRANSITIONS: [Tr(dst="greeting_node", cnd=cnd.ExactMatch("/start"))]},
        "greeting_node": {
            RESPONSE: "Hi! Do you want me to tell you a joke?",
            TRANSITIONS: [
                Tr(dst="tell_joke_node", cnd=cnd.ExactMatch("yes")),
                Tr(dst="bye_node", cnd=cnd.ExactMatch("no")),
            ],
        },
        "tell_joke_node": {
            RESPONSE: "",
            PRE_RESPONSE: {"joke_service": RandomJoke()},
            TRANSITIONS: [
                Tr(dst=dst.Current(), cnd=cnd.ExactMatch("no")),
                Tr(dst="bye_node", cnd=cnd.ExactMatch("yes")),
            ],
        },
        "bye_node": {
            RESPONSE: "I am glad! Bye-bye",
            TRANSITIONS: [Tr(dst="start_node")],
        },
        "fallback_node": {
            RESPONSE: "That was against the rules",
            TRANSITIONS: [Tr(dst="greeting_node")],
        },
    },
}

pipeline = Pipeline(
    ping_pong_script,
    start_label=("flow", "start_node"),
    fallback_label=("flow", "fallback_node"),
)

if __name__ == "__main__":
    pipeline.run()
