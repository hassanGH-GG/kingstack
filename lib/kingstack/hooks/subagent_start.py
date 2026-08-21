"""SubagentStart: make model, effort, role, and task visible at spawn time."""


def handle(event, runtime) -> dict:
    payload = event["payload"]
    task = str(payload.get("task") or payload.get("description") or "agent")[:60]
    model = payload.get("model") or "inherit"
    effort = payload.get("effort") or "inherit"
    role = payload.get("role") or payload.get("subagent_type") or "default"
    flag = " ⚠ no model set" if model == "inherit" else ""
    return {
        "systemMessage": "↳ spawn [{}] {} · model={} effort={}{}".format(
            role, task, model, effort, flag
        )
    }
